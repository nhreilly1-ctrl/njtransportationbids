import unittest
from unittest.mock import patch

from app import main as app_main
from app import notice_routes as notice_app
from app.core.corridors import (
    classify_location,
    enrich_location,
    location_display,
    map_query,
    map_url,
    normalize_reference_text,
)
from app.core.geography import classify_geography


def _classify(title, **fields):
    record = {"title": title}
    record.update(fields)
    return classify_location(record)


class CorridorExtractionTests(unittest.TestCase):
    def test_state_route_span_yields_one_corridor(self):
        result = _classify("Route 33, Bentley Road to Route 33B")
        self.assertIn("NJ-33", result["corridors"])

    def test_spaced_em_dash_interstate_is_an_interstate_not_a_state_route(self):
        result = _classify("Route I — 280 vegetation management")
        self.assertEqual(result["corridors"], ["I-280"])
        self.assertNotIn("NJ-280", result["corridors"])

    def test_dotted_county_route_in_all_caps_title(self):
        result = _classify("MILLING & RESURFACING SPRING VALLEY ROAD (C.R. 601)")
        self.assertEqual(result["corridors"], ["CR-601"])

    def test_route_list_expands_with_shared_designation_and_structure(self):
        result = _classify("Rt. 30, 40 and 47 Drawbridges ITS improvements")
        self.assertEqual(result["corridors"], ["US-30", "US-40", "NJ-47"])
        self.assertIn("drawbridge", result["structure_types"])

    def test_named_bridge_yields_structure_without_corridor_or_county(self):
        record = {"title": "Ben Franklin Bridge Masonry Rehabilitation Camden Anchorage"}
        location = classify_location(record)
        self.assertEqual(location["corridors"], [])
        self.assertIn("bridge", location["structure_types"])
        geography = classify_geography(dict(record, **location))
        self.assertEqual(geography["counties"], [])

    def test_contract_and_rfp_identifiers_are_not_corridors(self):
        self.assertEqual(_classify("Contract No. 21-I")["corridors"], [])
        self.assertEqual(_classify("RFP-6000003421")["corridors"], [])
        self.assertEqual(_classify("NJDOT TP — 842 resurfacing program")["corridors"], [])
        self.assertEqual(_classify("RM-202112 Extra Heavy Duty Towing")["corridors"], [])

    def test_corridor_never_populates_counties(self):
        record = {"title": "I-287 Bridge Deck Replacement", "source_id": "state-njdot-construction"}
        enrich_location(record)
        self.assertEqual(record["corridors"], ["I-287"])
        geography = classify_geography(record)
        self.assertEqual(geography["counties"], [])
        self.assertEqual(geography["coverage_scope"], "UNRESOLVED")

    def test_surface_form_variants_normalize_to_one_identifier(self):
        for surface in ("Route 33", "Rt. 33", "NJ 33", "NJ-33"):
            self.assertEqual(
                _classify(f"{surface} resurfacing")["corridors"], ["NJ-33"], surface
            )
        # "Route 130" is US-130 in every surface form once renumbered.
        for surface in ("Route 130", "Rt. 130", "US 130"):
            self.assertEqual(
                _classify(f"{surface} resurfacing")["corridors"], ["US-130"], surface
            )
        self.assertEqual(_classify("US 40 drainage")["corridors"], ["US-40"])
        self.assertEqual(_classify("U.S. 40 drainage")["corridors"], ["US-40"])
        self.assertEqual(_classify("Interstate 287 ramp")["corridors"], ["I-287"])
        self.assertEqual(_classify("I-295 sign structures")["corridors"], ["I-295"])

    def test_generic_prefix_on_interstate_and_us_numbers_renumbers_by_system(self):
        # NJ's 1953 renumbering left no state routes sharing an interstate or
        # US number, so "Route 295" is I-295 and "Rt 1" is US-1 — a closed
        # factual set, not an inference.
        self.assertEqual(_classify("Route 195, Route 295 to Route 9")["corridors"],
                         ["I-195", "I-295", "US-9"])
        self.assertEqual(_classify("Rt 287/202 to Ramapo River")["corridors"],
                         ["I-287", "US-202"])
        # Suffixed numbers keep their surface system.
        self.assertEqual(_classify("Rt 1, Rt 1B to Ryder Ln (CR 617)")["corridors"],
                         ["US-1", "NJ-1B", "CR-617"])
        # State-route numbers stay state routes.
        self.assertEqual(_classify("NJ 138 and NJ 72 drainage")["corridors"],
                         ["NJ-138", "NJ-72"])

    def test_state_and_county_routes_with_the_same_number_stay_distinct(self):
        result = _classify("Route 1 improvements near CR 1 culvert")
        self.assertIn("US-1", result["corridors"])
        self.assertIn("CR-1", result["corridors"])
        self.assertIn("culvert", result["structure_types"])

    def test_route_number_bounded_to_three_digits(self):
        self.assertEqual(_classify("Route 6000003421 program")["corridors"], [])
        self.assertEqual(_classify("NJ 2026 Bid Schedule")["corridors"], [])

    def test_lowercase_nj_and_us_are_not_route_designations(self):
        self.assertEqual(_classify("give us 3 copies of the proposal")["corridors"], [])
        self.assertEqual(_classify("send nj 5 business days notice")["corridors"], [])

    def test_slash_list_of_interstates(self):
        result = _classify("Vegetation Safety Management Project I-280, I-195/295")
        self.assertEqual(result["corridors"], ["I-280", "I-195", "I-295"])

    def test_named_corridors_are_recognized(self):
        self.assertEqual(
            _classify("Garden State Parkway Milepost 103.5 to 106.3 paving")["corridors"],
            ["Garden State Parkway"],
        )
        self.assertEqual(
            _classify("New Jersey Turnpike Interchange 8A improvements")["corridors"][:1],
            ["NJ Turnpike"],
        )

    def test_excerpt_is_route_evidence_when_title_is_silent(self):
        result = _classify(
            "Engineering Design Services",
            notice_excerpt="Rehabilitation of the Route 72 causeway",
        )
        self.assertEqual(result["corridors"], ["NJ-72"])
        self.assertIn('notice_excerpt:"Route 72"', result["location_evidence"])


class StructureExtractionTests(unittest.TestCase):
    def test_vocabulary_terms_extract_with_plurals(self):
        result = _classify("Toll plazas, culverts and one viaduct near the interchange")
        for expected in ("toll plaza", "culvert", "viaduct", "interchange"):
            self.assertIn(expected, result["structure_types"])

    def test_drawbridge_does_not_also_emit_bridge(self):
        result = _classify("Rt. 30 Drawbridges ITS improvements")
        self.assertIn("drawbridge", result["structure_types"])
        self.assertNotIn("bridge", result["structure_types"])


class MunicipalityExtractionTests(unittest.TestCase):
    def test_type_of_name_grammar(self):
        result = _classify("Improvements for the City of Trenton signal system")
        self.assertEqual(result["municipalities"], ["City of Trenton"])

    def test_name_type_grammar_in_all_caps(self):
        result = _classify("MILLING VARIOUS ROADS FRANKLIN TOWNSHIP")
        self.assertEqual(result["municipalities"], ["Franklin Township"])

    def test_lead_grammar_trims_project_vocabulary_on_the_right(self):
        result = _classify("Township of Robbinsville Bridge Repairs")
        self.assertEqual(result["municipalities"], ["Township of Robbinsville"])

    def test_trail_grammar_trims_project_vocabulary_on_the_left(self):
        result = _classify("RESURFACING OF VARIOUS ROADS IN JERSEY CITY")
        self.assertEqual(result["municipalities"], ["Jersey City"])

    def test_out_of_state_and_non_municipal_places_are_excluded(self):
        self.assertEqual(_classify("Trenton NJ and Morrisville PA approach spans")["municipalities"], [])
        self.assertEqual(_classify("New York City ferry terminal")["municipalities"], [])
        self.assertEqual(
            _classify("Atlantic City Expressway resurfacing")["municipalities"], []
        )

    def test_agency_address_is_not_municipality_evidence(self):
        # Only notice text fields are read; an address field is never consulted.
        result = classify_location(
            {"title": "Guiderail replacement", "agency_address": "1 City of Newark Plaza"}
        )
        self.assertEqual(result["municipalities"], [])


class DisplayAndMapTests(unittest.TestCase):
    def test_location_display_prefers_corridor_and_municipality(self):
        record = enrich_location({"title": "I-287 culvert repairs, Borough of Somerville"})
        self.assertEqual(location_display(record), "I-287 · Borough of Somerville")

    def test_location_display_empty_without_evidence(self):
        record = enrich_location({"title": "Guiderail and attenuator maintenance"})
        self.assertEqual(location_display(record), "")

    def test_map_query_uses_municipality_before_corridor_and_never_invents(self):
        muni = enrich_location({"title": "Route 33 resurfacing, City of Trenton"})
        self.assertEqual(map_query(muni), "City of Trenton, New Jersey")
        corridor = enrich_location({"title": "Route 33 resurfacing"})
        self.assertEqual(map_query(corridor), "NJ-33, New Jersey")
        none = enrich_location({"title": "Guiderail maintenance"})
        self.assertEqual(map_query(none), "")
        self.assertEqual(map_url(none), "")

    def test_map_url_is_a_google_maps_search_link(self):
        record = enrich_location({"title": "Route 33 resurfacing, City of Trenton"})
        self.assertEqual(
            map_url(record),
            "https://www.google.com/maps/search/?api=1&query=City+of+Trenton%2C+New+Jersey",
        )

    def test_normalize_reference_text_unifies_dashes_and_ligatures(self):
        self.assertEqual(normalize_reference_text("TP — 842"), "TP-842")
        self.assertEqual(normalize_reference_text("traﬃc"), "traﬃc")  # unknown ligatures untouched
        self.assertEqual(normalize_reference_text("ﬁnal I – 78  plan’s"), "final I-78 plan's")


class PublicSurfaceTests(unittest.TestCase):
    @staticmethod
    def _opp(record_id, title, **overrides):
        record = {
            "id": record_id,
            "_canonical_notice": True,
            "title": title,
            "status": "open",
            "source_status": "open",
            "source_id": "state-njdot-construction",
            "source_name": "NJDOT Construction",
            "source_tier": "state",
            "source_url": "https://agency.example/bids",
            "official_url": f"https://agency.example/bids/{record_id}",
            "county": "",
            "notice_type": "construction",
            "notice_subtype": "construction",
            "due_date_raw": "12/31/68",
            "contract_number": f"T-{record_id}",
            "access_type": "Public access",
            "platform": "Agency website",
            "crawled_at": "2026-08-22T12:00:00+00:00",
        }
        record.update(overrides)
        return record

    def test_homepage_shows_corridor_chips_location_and_map_link(self):
        records = [
            self._opp("i287", "I-287 Bridge Deck Replacement, Borough of Somerville"),
            self._opp("plain", "Guiderail and attenuator maintenance"),
        ]
        with (
            patch.object(app_main, "load_public_opps", return_value=records),
            patch.object(app_main, "load_public_sources", return_value=[]),
        ):
            html = app_main.app.test_client().get("/").get_data(as_text=True)

        self.assertIn('class="corridor-chip"', html)
        self.assertIn("/notices?corridor=I-287", html)
        self.assertIn("I-287 · Borough of Somerville", html)
        self.assertIn("https://www.google.com/maps/search/?api=1&amp;query=Borough+of+Somerville", html)
        # A record with no evidenced location keeps the county language and no map link.
        self.assertIn("County not stated in notice", html)

    def test_notices_list_filters_by_corridor_field(self):
        on_corridor = {
            "id": "on-corridor",
            "title": "I-287 culvert lining",
            "status": "open",
            "notice_type": "construction",
            "source_name": "NJDOT",
            "source_tier": "state",
            "corridors": ["I-287"],
            "due_date_parsed": "2099-12-31",
        }
        off_corridor = {
            "id": "off-corridor",
            "title": "Route 33 resurfacing",
            "status": "open",
            "notice_type": "construction",
            "source_name": "NJDOT",
            "source_tier": "state",
            "corridors": ["NJ-33"],
            "due_date_parsed": "2099-12-31",
        }
        with (
            patch.object(notice_app, "_load_notices", return_value=[on_corridor, off_corridor]),
            patch.object(notice_app, "_load_crawl_log", return_value=[]),
        ):
            client = app_main.app.test_client()
            filtered = client.get("/notices?corridor=I-287").get_data(as_text=True)
            unfiltered = client.get("/notices").get_data(as_text=True)

        self.assertIn("I-287 culvert lining", filtered)
        self.assertNotIn("Route 33 resurfacing", filtered)
        self.assertIn("Route 33 resurfacing", unfiltered)

    def test_detail_page_shows_corridor_structure_and_map_rows(self):
        records = [self._opp("i287", "I-287 Bridge Deck Replacement, Borough of Somerville")]
        with patch.object(app_main, "load_public_opps", return_value=records):
            html = app_main.app.test_client().get("/opportunities/i287").get_data(as_text=True)

        self.assertIn(">Corridor</td>", html)
        self.assertIn("I-287", html)
        self.assertIn(">Structure</td>", html)
        self.assertIn("Bridge", html)
        self.assertIn(">Municipality</td>", html)
        self.assertIn("Borough of Somerville", html)
        self.assertIn("View on map", html)


if __name__ == "__main__":
    unittest.main()
