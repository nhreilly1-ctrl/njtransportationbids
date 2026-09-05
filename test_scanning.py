import unittest
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import patch

from app import main, notice_routes
from app.core.scanning import closing_soon, first_seen_today, matches_search
from app.core.corridors import map_query, enrich_location
from crawlers import notice_runner


class ScanTrustTests(unittest.TestCase):
    def test_date_only_calendar_is_all_day_through_real_route(self):
        record = dict(id="date-only", title="Bridge repairs", notice_type="construction",
                      _canonical_notice=True, source_tier="county",
                      source_name="Test agency", due_date_raw="09/10/2099",
                      official_url="https://example.com/bid")
        with patch.object(main, "load_public_opps", return_value=[record]):
            response = main.app.test_client().get("/opportunities/date-only/calendar.ics")
        self.assertEqual(response.status_code, 200)
        calendar = response.get_data(as_text=True)
        self.assertIn("DTSTART;VALUE=DATE:20990910", calendar)
        self.assertIn("DTEND;VALUE=DATE:20990911", calendar)
        self.assertNotRegex(calendar, r"DT(?:START|END)[^\r\n]*T\d{6}")

    def test_map_search_preserves_crossing_and_does_not_write_geography(self):
        record = dict(corridors=["US-1"], directional_route_labels=["Route 1 NB"],
                      crossing_phrases=["Bridge over Raritan River"],
                      counties=["Middlesex"], geography_provenance="NOTICE_TEXT")
        before = deepcopy(record)
        query = map_query(record)
        for text in ("Route 1 NB", "Bridge over Raritan River", "Middlesex County"):
            self.assertIn(text, query)
        self.assertEqual(record, before)
        coastal = dict(municipalities=["Ocean City"], counties=[], corridors=["NJ-52"])
        before = deepcopy(coastal)
        query = map_query(coastal)
        self.assertIn("Ocean City", query)
        self.assertNotIn("Ocean County", query)
        self.assertEqual(coastal, before)

    def render_project(self, **changes):
        record = dict(id="project-test", title="Route 1 bridge over Raritan River",
                      record_type="professional_services", status="open",
                      source_name="NJDOT", county_display="County not stated in notice",
                      official_url="https://example.com/official", corridors=["US-1"],
                      map_url="https://www.google.com/maps/search/?api=1&query=bridge",
                      due_date_raw="09/10/2026", due_date_parsed="2026-09-10",
                      deadline_display="Thu, Sep 10, 2026 (time not published)",
                      days_until_due=5, notice_excerpt="Published project description")
        record.update(changes)
        with main.app.test_request_context("/opportunities/project-test"):
            return main.render_template("opportunity_detail.html", opp=record,
                                        related=[], readiness=None, source_total=47,
                                        seo_title=record["title"], seo_description="Project notice")

    def test_project_actions_precede_summary_without_duplicates(self):
        html = self.render_project()
        self.assertLess(html.index('class="project-actions"'), html.index("Opportunity summary"))
        for event in ("official_source_click", "map_click", "calendar_add"):
            self.assertEqual(html.count('data-analytics-event="' + event + '"'), 1)
        self.assertIn("not verified project limits", html)
        self.assertIn("time not published", html)
        self.assertNotIn("12:00 AM", html)
        self.assertIn("County not stated in notice", html)

    def test_project_conflict_and_closed_states_disable_calendar(self):
        html = self.render_project(deadline_conflict=True)
        self.assertIn("Deadline needs confirmation", html)
        self.assertNotIn('data-analytics-event="calendar_add"', html)
        self.assertNotIn("5 days remaining", html)
        html = self.render_project(status="expired")
        self.assertIn("This opportunity is closed", html)
        self.assertNotIn('data-analytics-event="calendar_add"', html)
        record = dict(id="project-test", status="open", due_date_parsed="2026-09-10", deadline_conflict=True)
        with patch.object(main, "load_public_opps", return_value=[record]), patch.object(main, "enrich", side_effect=lambda x: x):
            self.assertEqual(main.app.test_client().get("/opportunities/project-test/calendar.ics").status_code, 404)

    def test_project_without_deadline_or_map_states_absence(self):
        html = self.render_project(due_date_raw=None, due_date_parsed=None, map_url=None)
        self.assertIn("Deadline not published", html)
        self.assertNotIn('data-analytics-event="map_click"', html)
        self.assertNotIn('data-analytics-event="calendar_add"', html)

    def test_preview_and_admin_do_not_load_google_analytics(self):
        client = main.app.test_client()
        for path, base in (("/resources", "http://localhost"), ("/admin/login", "https://www.njtransportationbids.com")):
            html = client.get(path, base_url=base).get_data(as_text=True)
            self.assertNotIn('src="https://www.googletagmanager.com', html)
        html = client.get("/resources", base_url="https://www.njtransportationbids.com").get_data(as_text=True)
        self.assertIn('src="https://www.googletagmanager.com', html)

    def test_conflicting_dates_are_not_closing_soon(self):
        record = dict(status="open", due_date_parsed="2000-01-01", deadline_conflict=True, urgent=True)
        self.assertFalse(closing_soon(record))
        self.assertEqual(main.group_opportunity_scan([record])[3], [record])
        self.assertEqual(notice_routes._group_by_urgency([record])[3], [record])
        self.assertEqual(notice_routes._filter_notices([record], status_filter="urgent"), [])

    def test_closing_window_and_exact_time(self):
        now = datetime(2026, 9, 4, 20, tzinfo=timezone.utc)
        for due, expected in (("2026-09-03", False), ("2026-09-04", True), ("2026-09-11", True), ("2026-09-12", False)):
            self.assertEqual(closing_soon(dict(status="open", due_date_parsed=due), now), expected)
        self.assertFalse(closing_soon(dict(status="open", due_date_parsed="2026-09-04", deadline_at="2026-09-04T19:00:00Z"), now))

    def test_first_seen_uses_eastern_not_refresh_date(self):
        now = datetime(2026, 9, 5, 1, tzinfo=timezone.utc)
        self.assertFalse(first_seen_today(dict(crawled_at=now.isoformat()), now))
        self.assertTrue(first_seen_today(dict(first_seen_at="2026-09-04T14:00:00Z"), now))
        self.assertFalse(first_seen_today(dict(first_seen_at="2026-09-04T01:00:00Z"), now))

    def test_merge_preserves_known_and_unknown_discovery(self):
        old = dict(id="a", source_id="x", contract_number="DP-1", first_seen_at="2026-08-01T14:00:00Z")
        result = notice_runner._merge([old], [dict(old, first_seen_at="wrong")])[0]
        self.assertEqual(result["first_seen_at"], old["first_seen_at"])
        legacy = dict(id="b", source_id="x", contract_number="DP-2")
        self.assertIsNone(notice_runner._merge([legacy], [legacy.copy()])[0]["first_seen_at"])
        amended = dict(old, id="changed-title")
        self.assertEqual(notice_runner._merge([old], [amended])[-1]["first_seen_at"], old["first_seen_at"])
        with patch.object(notice_runner, "_now", return_value="2026-09-04T14:00:00Z"):
            self.assertEqual(notice_runner._merge([], [dict(id="new")])[0]["first_seen_at"], "2026-09-04T14:00:00Z")

    def test_search_contract_and_word_order(self):
        record = dict(title="Bridge over Raritan River", contract_number="DP-26107", corridors=["US-1"])
        self.assertTrue(matches_search(record, "DP 26107"))
        self.assertTrue(matches_search(record, "Raritan bridge"))
        self.assertTrue(matches_search(record, "US 1"))
        self.assertFalse(matches_search(record, "2610"))

    def test_intersection_preserves_all_roads(self):
        record = enrich_location(dict(title="Intersection improvements at County Route 3 (Tennent Road) and Spring Valley Road / Harbor Road in the Township of Marlboro"))
        query = map_query(record)
        for road in ("Tennent Road", "Spring Valley Road", "Harbor Road", "Marlboro"):
            self.assertIn(road, query)

    def test_multisite_search_does_not_pair_first_route_and_county(self):
        query = map_query(dict(corridors=["I-278", "I-287"], counties=["Bergen", "Union"], geography_provenance="NOTICE_TEXT"))
        for value in ("I-278", "I-287", "Bergen", "Union"):
            self.assertIn(value, query)


if __name__ == "__main__":
    unittest.main()
