import unittest
from unittest.mock import patch

from app.core.geography import NJ_COUNTIES, classify_geography
from app import main as app_main


def classify(title="", county="", source_id="state-njdot-construction", **extra):
    return classify_geography(
        {
            "title": title,
            "county": county,
            "source_id": source_id,
            **extra,
        }
    )


class GeographyClassifierTests(unittest.TestCase):
    def test_all_21_counties_are_canonicalized(self):
        emitted = set()
        for county in NJ_COUNTIES:
            with self.subTest(county=county):
                result = classify(title=f"Road improvements in {county} County")
                self.assertEqual(result["counties"], [county])
                self.assertEqual(result["coverage_scope"], "SINGLE_COUNTY")
                emitted.update(result["counties"])
        self.assertEqual(emitted, set(NJ_COUNTIES))

    def test_route_33_multi_county_title_overrides_statewide_default(self):
        result = classify(
            title=(
                "Route 33 pavement preservation, Township of Monroe, Township of Millstone "
                "and Township of Manalapan, Middlesex County and Monmouth County"
            ),
            county="Statewide",
        )
        self.assertEqual(result["counties"], ["Middlesex", "Monmouth"])
        self.assertEqual(result["coverage_scope"], "MULTI_COUNTY")
        self.assertEqual(result["geography_confidence"], "MEDIUM")
        self.assertTrue(result["geography_conflict"])

    def test_plural_county_lists_handle_oxford_comma_and_cape_may(self):
        result = classify(
            title=(
                "Atlantic, Burlington, Camden, Cape May, Cumberland, Gloucester, "
                "and Salem Counties"
            )
        )
        self.assertEqual(
            result["counties"],
            ["Atlantic", "Burlington", "Camden", "Cape May", "Cumberland", "Gloucester", "Salem"],
        )

    def test_counties_of_prefix_and_ampersand_list(self):
        prefixed = classify(title="Counties of Atlantic, Burlington and Mercer")
        ampersand = classify(title="Monmouth & Middlesex County")
        self.assertEqual(prefixed["counties"], ["Atlantic", "Burlington", "Mercer"])
        self.assertEqual(ampersand["counties"], ["Middlesex", "Monmouth"])

    def test_bistate_agency_counties_are_hints_not_filter_values(self):
        result = classify(county="Warren/Hunterdon/Mercer", source_id="state-drjtbc-construction")
        self.assertEqual(result["counties"], [])
        self.assertEqual(result["coverage_scope"], "BISTATE")
        self.assertEqual(result["geography_confidence"], "LOW")
        self.assertEqual(result["geography_provenance"], "AGENCY_JURISDICTION")
        self.assertEqual(result["agency_county_hint"], "Warren/Hunterdon/Mercer")

    def test_agency_county_default_is_not_filterable_without_notice_evidence(self):
        result = classify(title="Legal Notices", county="Essex", source_id="county-essex")
        self.assertEqual(result["counties"], [])
        self.assertEqual(result["coverage_scope"], "UNRESOLVED")
        self.assertEqual(result["agency_county_hint"], "Essex")
        self.assertEqual(result["geography_provenance"], "AGENCY_JURISDICTION")

    def test_structured_official_county_field_remains_filterable(self):
        result = classify(
            title="Route 9 pavement preservation",
            county="Ocean",
            county_provenance="SOURCE_RECORD_FIELD",
        )
        self.assertEqual(result["counties"], ["Ocean"])
        self.assertEqual(result["coverage_scope"], "SINGLE_COUNTY")
        self.assertEqual(result["geography_provenance"], "SOURCE_RECORD_FIELD")

    def test_notice_excerpt_can_supply_explicit_county_evidence(self):
        result = classify(
            title="Roadway reconstruction",
            county="Statewide",
            notice_excerpt="Work is in the City of Plainfield, Union County, New Jersey.",
        )
        self.assertEqual(result["counties"], ["Union"])
        self.assertEqual(result["geography_provenance"], "NOTICE_TEXT")
        self.assertIn('notice_excerpt:"Union County"', result["geography_evidence"])

    def test_multiple_dp_identifiers_require_segmentation_review(self):
        result = classify(
            title="Camden County bridge, DP No: 25132. Essex County paving, DP No: 26105.",
            county="Statewide",
        )
        self.assertEqual(result["counties"], [])
        self.assertEqual(result["coverage_scope"], "UNRESOLVED")
        self.assertTrue(result["geography_review_required"])
        self.assertEqual(result["county_display"], "Location requires review")

    def test_regional_tokens_never_expand_to_counties(self):
        for region in ("North", "Central", "South", "South Region", "Central & North", "Northern New Jersey", "Various"):
            with self.subTest(region=region):
                result = classify(county=region)
                self.assertEqual(result["counties"], [])
                self.assertEqual(result["coverage_scope"], "REGIONAL")
                self.assertEqual(result["region_raw"], region)

    def test_same_north_token_can_resolve_to_different_counties(self):
        warren = classify(title="Pavement Preservation North Contract 13, Warren County", county="Statewide")
        six_counties = classify(
            title="Drainage Restoration Contract, North - Bergen, Essex, Hudson, Morris, Passaic, and Union Counties",
            county="Statewide",
        )
        self.assertEqual(warren["counties"], ["Warren"])
        self.assertEqual(warren["region_raw"], "North")
        self.assertEqual(
            six_counties["counties"],
            ["Bergen", "Essex", "Hudson", "Morris", "Passaic", "Union"],
        )
        self.assertEqual(six_counties["region_raw"], "North")

    def test_proper_noun_traps_do_not_emit_false_counties(self):
        fixtures = {
            "HENRY HUDSON TRAIL BRIDGE IN KEYPORT, MONMOUTH COUNTY PARK SYSTEM": ["Monmouth"],
            "Gloucester City roadway improvements": [],
            "Ocean City boardwalk repairs": [],
            "Union City traffic signal upgrades": [],
            "Salem Street reconstruction in Newark": [],
            "Bergen Street reconstruction in Newark": [],
            "Passaic River bridge rehabilitation": [],
            "Mercer County Park roadway improvements": ["Mercer"],
        }
        for title, expected in fixtures.items():
            with self.subTest(title=title):
                self.assertEqual(classify(title=title)["counties"], expected)

    def test_explicit_statewide_and_unresolved_are_distinct(self):
        statewide = classify(title="Statewide traffic engineering term agreement", county="Statewide")
        unresolved = classify(title="Bridge inspection services", county="Statewide")
        self.assertEqual(statewide["coverage_scope"], "STATEWIDE")
        self.assertEqual(unresolved["coverage_scope"], "UNRESOLVED")
        self.assertEqual(unresolved["county_display"], "County not stated in notice")

    def test_bistate_source_is_not_forced_to_statewide(self):
        result = classify(
            title="George Washington Bridge transformer replacement",
            county="Statewide",
            source_id="state-panynj-construction",
        )
        self.assertEqual(result["coverage_scope"], "BISTATE")
        self.assertEqual(result["counties"], [])
        self.assertEqual(result["county_display"], "Bi-state")

    def test_bistate_source_does_not_expand_even_explicit_county_text(self):
        result = classify(
            title="Bridge rehabilitation in Mercer County",
            county="Warren/Hunterdon/Mercer",
            source_id="state-drjtbc-construction",
        )
        self.assertEqual(result["coverage_scope"], "BISTATE")
        self.assertEqual(result["counties"], [])
        self.assertEqual(result["geography_provenance"], "NOTICE_TEXT")

    def test_output_is_idempotent_and_only_contains_canonical_counties(self):
        record = {
            "title": "Gloucester and Salem Counties bridge maintenance",
            "county": "Statewide",
            "source_id": "state-njdot-construction",
        }
        first = classify_geography(record)
        second = classify_geography({**record, **first})
        self.assertEqual(first, second)
        self.assertTrue(set(first["counties"]).issubset(set(NJ_COUNTIES)))


class GeographyPublicPageTests(unittest.TestCase):
    route_33 = {
        "id": "route-33",
        "title": (
            "Route 33 pavement preservation, Township of Monroe, Township of Millstone "
            "and Township of Manalapan, Middlesex County and Monmouth County"
        ),
        "source_id": "state-njdot-construction",
        "source_name": "NJDOT Construction Services",
        "source_tier": "state",
        "county": "Statewide",
        "notice_type": "construction",
        "status": "open",
        "source_status": "open",
        "due_date_raw": "12/31/2099",
        "official_url": "https://example.com/route-33",
    }

    def test_county_filter_uses_normalized_multi_county_values(self):
        with patch.object(app_main, "load_public_opps", return_value=[self.route_33]):
            client = app_main.app.test_client()
            middlesex = client.get("/bids/construction?county=Middlesex").get_data(as_text=True)
            monmouth = client.get("/bids/construction?county=Monmouth").get_data(as_text=True)
            bergen = client.get("/bids/construction?county=Bergen").get_data(as_text=True)

        self.assertIn("Route 33 pavement preservation", middlesex)
        self.assertIn("Route 33 pavement preservation", monmouth)
        self.assertNotIn("Route 33 pavement preservation", bergen)
        self.assertNotIn("Statewide</option>", middlesex)

    def test_csv_exposes_raw_and_normalized_geography(self):
        with patch.object(app_main, "load_public_opps", return_value=[self.route_33]):
            response = app_main.app.test_client().get("/export/opportunities.csv")

        csv_text = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "county,county_provenance,counties,coverage_scope,region_raw,geography_confidence,geography_provenance",
            csv_text,
        )
        self.assertIn("Statewide,,Middlesex|Monmouth,MULTI_COUNTY", csv_text)


if __name__ == "__main__":
    unittest.main()
