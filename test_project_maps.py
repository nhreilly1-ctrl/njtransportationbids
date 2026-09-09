import copy
import unittest

from app.core.project_maps import project_map_links
from app.main import enrich, app
from unittest.mock import patch
import app.main as main


class ProjectMapTests(unittest.TestCase):
    def test_verified_bridge_is_reusable_but_direction_and_agency_are_required(self):
        record = {"title": "Rt 1 NB, Bridge over Raritan River", "source_id": "state-njdot-profserv-upcoming"}
        self.assertEqual(project_map_links(record)[0]["kind"], "verified_structure")
        for title in ("Rt 1 SB, Bridge over Raritan River", "Rt 1, Bridge over Raritan River", "Rt 1 NB, Bridge over Millstone River", "Rt 1 NB and Route 9, Bridge over Raritan River"):
            self.assertNotEqual(project_map_links({**record, "title": title})[0]["kind"], "verified_structure")
        self.assertNotEqual(project_map_links({**record, "source_id": "county-morris"})[0]["kind"], "verified_structure")

    def test_road_drops_house_number_trap_without_changing_evidence(self):
        record = {"title": "MILLING & RESURFACING SPRING VALLEY ROAD (C.R. 601)", "source_id": "county-morris", "agency_county_hint": "Morris", "counties": []}
        before = copy.deepcopy(record)
        link = project_map_links(record)[0]
        self.assertEqual(link["query"], "Spring Valley Road, Morris County, New Jersey")
        self.assertEqual(record, before)

    def test_baileys_is_only_road_search(self):
        link = project_map_links({"title": "Bailey's Mill Road, Bridge over Rt. 287 (NB & SB)"})[0]
        self.assertEqual(link["query"], "Bailey's Mill Road, New Jersey")
        self.assertEqual(link["kind"], "road_search")

    def test_receiving_office_never_maps(self):
        record = {"title": "BID # 26-40 SPECIFICATIONS FOR FY 2026 FEDERAL ROAD PROGRAM", "notice_excerpt": "Sealed bids received at 164 West Broad Street, Bridgeton, New Jersey", "road_names": ["West Broad Street"], "municipalities": ["Bridgeton"]}
        self.assertEqual(project_map_links(record), [])

    def test_multi_route_has_separate_links_not_arbitrary_county_pairs(self):
        links = project_map_links({"title": "Drainage restoration I-278, I-280, I-287", "counties": ["Bergen", "Essex"], "geography_provenance": "NOTICE_TEXT"})
        self.assertEqual([x["query"] for x in links], ["I-278, New Jersey", "I-280, New Jersey", "I-287, New Jersey"])

    def test_explicit_intersection_preserves_both_named_legs(self):
        links = project_map_links({"title": "DESIGN OF INTERSECTION IMPROVEMENTS AT COUNTY ROUTE 3 (TENNENT ROAD) AND SPRING VALLEY ROAD / HARBOR ROAD IN THE TOWNSHIP OF MARLBORO"})
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0]["query"], "Tennent Road & Spring Valley Road, Township of Marlboro, New Jersey")
        self.assertIn("Tennent Road & Harbor Road", links[1]["query"])

    def test_rendered_verified_link_has_official_evidence(self):
        record = {"id": "map-test", "title": "Rt 1 NB, Bridge over Raritan River", "source_id": "state-njdot-construction", "status": "upcoming"}
        with patch.object(main, "load_public_opps", return_value=[record]):
            response = app.test_client().get("/opportunities/map-test")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"View Morris Goodkind Bridge", response.data)
        self.assertIn(b"NJDOT location evidence", response.data)

    def test_enrichment_preserves_geography_and_exposes_multi_links(self):
        record = enrich({"title": "I-278 and I-280 drainage", "id": "multi"})
        self.assertEqual(len(record["map_links"]), 2)
        self.assertEqual(record["map_url"], "")
        self.assertFalse(record["counties"])

    def test_multiple_actions_render_without_a_merged_map_query(self):
        record = {"id": "multi", "title": "I-278 and I-280 drainage", "status": "upcoming"}
        with patch.object(main, "load_public_opps", return_value=[record]):
            response = app.test_client().get("/opportunities/multi")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'data-analytics-event="map_click"'), 2)
        self.assertIn(b"View corridor: I-278", response.data)
        self.assertIn(b"View corridor: I-280", response.data)

    def test_cumberland_detail_withholds_receipt_office_map(self):
        record = {"id": "office", "title": "FY 2026 FEDERAL ROAD PROGRAM", "status": "upcoming", "notice_excerpt": "Receive bids at 164 West Broad Street"}
        with patch.object(main, "load_public_opps", return_value=[record]):
            response = app.test_client().get("/opportunities/office")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'data-analytics-event="map_click"', response.data)
        self.assertNotIn("West Broad Street", enrich(record)["location_display"])


if __name__ == "__main__":
    unittest.main()
