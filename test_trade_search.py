import copy
import unittest
from unittest.mock import patch

from app.core.scanning import matches_search
import app.main as main
import app.notice_routes as notice_routes


class TradeSearchTests(unittest.TestCase):
    def test_paving_matches_existing_project_language(self):
        for title in ("MILLING & RESURFACING GREEN POND ROAD", "Pavement Preservation North Contract 13", "Route 1 pavement reconstruction", "Asphalt overlay on Main Street"):
            with self.subTest(title=title):
                self.assertTrue(matches_search({"title": title}, "paving"))

    def test_drainage_and_bridge_language(self):
        for title in ("Culvert replacement", "Stormwater improvements", "Storm sewer installation"):
            self.assertTrue(matches_search({"title": title}, "drainage"))
        self.assertTrue(matches_search({"title": "Inspection of bridges"}, "bridge inspection"))
        self.assertTrue(matches_search({"title": "Viaduct repairs"}, "bridge"))

    def test_multiple_query_terms_still_all_required(self):
        record = {"title": "Milling and resurfacing", "source_name": "Morris County", "contract_number": "M25-31"}
        self.assertTrue(matches_search(record, "paving Morris"))
        self.assertFalse(matches_search(record, "paving Somerset"))
        self.assertTrue(matches_search(record, "paving M25-31"))
        self.assertFalse(matches_search(record, "paving M25-30"))

    def test_no_substrings_agency_expansion_or_machinery_guess(self):
        for record in ({"title": "Landscaping supplies"}, {"title": "Milling machine rental"}, {"title": "Office supplies", "source_name": "Pavement Preservation Division"}, {"title": "Resurfacington office equipment"}):
            self.assertFalse(matches_search(record, "paving"))
        self.assertFalse(matches_search({"title": "Office furniture", "source_name": "Stormwater Utility"}, "drainage"))

    def test_search_never_writes_source_or_geography(self):
        record = {"title": "Pavement preservation", "counties": [], "notice_excerpt": "Work along US 1"}
        before = copy.deepcopy(record)
        self.assertTrue(matches_search(record, "paving"))
        self.assertEqual(record, before)

    def test_construction_route_uses_trade_expansion(self):
        records = [{"id": "paving-fixture", "_canonical_notice": True, "title": "Milling and resurfacing Green Pond Road", "notice_type": "construction", "notice_subtype": "construction", "status": "open", "source_name": "Morris County", "due_date_raw": "12/31/2068"}]
        with patch.object(main, "load_public_opps", return_value=records):
            response = main.app.test_client().get("/bids/construction?q=paving")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Milling and resurfacing Green Pond Road", response.data)

    def test_notices_filters_use_same_matcher(self):
        record = {"id": "pave", "title": "Pavement preservation", "status": "open"}
        self.assertEqual(notice_routes._filter_notices([record], q="paving"), [record])


if __name__ == "__main__":
    unittest.main()
