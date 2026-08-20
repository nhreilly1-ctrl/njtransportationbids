import unittest
from datetime import date, datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from app import main as app_main
from app.core.deadlines import deadline_is_past, normalize_deadline


class DeadlineNormalizationTests(unittest.TestCase):
    def test_utc_timestamp_is_rendered_in_eastern_time(self):
        record = normalize_deadline(
            {"due_date_raw": "2026-08-25T20:00:47.395Z"},
            today=date(2026, 8, 20),
        )

        self.assertEqual(record["deadline_at"], "2026-08-25T20:00:47.395000Z")
        self.assertEqual(record["deadline_local"], "2026-08-25T16:00:47.395000-04:00")
        self.assertEqual(record["deadline_display"], "Tue, Aug 25, 2026 at 4:00 PM ET")
        self.assertEqual(record["due_date_parsed"], "2026-08-25")
        self.assertFalse(record["deadline_timezone_assumed"])

    def test_local_timestamp_is_labeled_as_assumed_eastern(self):
        record = normalize_deadline(
            {"due_date_raw": "2026-09-09 15:00:00"},
            today=date(2026, 8, 20),
        )

        self.assertEqual(record["deadline_at"], "2026-09-09T19:00:00Z")
        self.assertEqual(
            record["deadline_display"],
            "Wed, Sep 9, 2026 at 3:00 PM ET (time zone assumed)",
        )
        self.assertTrue(record["deadline_timezone_assumed"])

    def test_explicit_eastern_sentence_is_parsed(self):
        record = normalize_deadline(
            {"due_date_raw": "2:00 PM Eastern Time (ET) on August 24, 2026"},
            today=date(2026, 8, 20),
        )

        self.assertEqual(record["deadline_at"], "2026-08-24T18:00:00Z")
        self.assertEqual(record["deadline_display"], "Mon, Aug 24, 2026 at 2:00 PM ET")
        self.assertEqual(record["deadline_timezone_source"], "explicit_eastern")

    def test_date_only_does_not_invent_a_time(self):
        record = normalize_deadline(
            {"due_date_raw": "August 25, 2026"},
            today=date(2026, 8, 20),
        )

        self.assertEqual(record["deadline_precision"], "date")
        self.assertIsNone(record["deadline_at"])
        self.assertEqual(record["deadline_display"], "Tue, Aug 25, 2026 (time not published)")

    def test_planning_window_stays_anticipated(self):
        record = normalize_deadline(
            {"due_date_raw": "Fall 2026", "status": "upcoming", "is_planned": True},
            today=date(2026, 8, 20),
        )

        self.assertEqual(record["deadline_precision"], "window")
        self.assertEqual(record["deadline_display"], "Fall 2026 (anticipated)")
        self.assertIsNone(record["due_date_parsed"])

    def test_exact_deadline_expires_after_instant_not_at_start_of_day(self):
        record = normalize_deadline({"due_date_raw": "2026-08-25T20:00:00Z"})
        before = datetime(2026, 8, 25, 15, 59, tzinfo=ZoneInfo("America/New_York"))
        after = datetime(2026, 8, 25, 16, 1, tzinfo=ZoneInfo("America/New_York"))

        self.assertFalse(deadline_is_past(record, before))
        self.assertTrue(deadline_is_past(record, after))


class PublicSourceLedgerTests(unittest.TestCase):
    def test_sources_page_includes_configured_zero_record_source_and_health(self):
        configured = [
            {
                "id": "state-one",
                "name": "Agency One",
                "source_tier": "state",
                "url": "https://agency.example/one",
                "crawl_freq": "daily",
            },
            {
                "id": "county-zero",
                "name": "Zero County Procurement",
                "source_tier": "county",
                "county": "Mercer",
                "url": "https://agency.example/zero",
                "crawl_freq": "daily",
                "allow_empty": True,
            },
        ]
        health = {
            "sources": [
                {
                    "source_id": "state-one",
                    "severity": "ok",
                    "status": "ok",
                    "last_crawl": "2026-08-20T18:00:00-04:00",
                    "last_count": 3,
                    "message": "Latest crawl completed normally.",
                },
                {
                    "source_id": "county-zero",
                    "severity": "ok",
                    "status": "ok",
                    "last_crawl": "2026-08-20T18:01:00-04:00",
                    "last_count": 0,
                    "message": "Crawl succeeded; no matching opportunities are currently listed.",
                },
            ]
        }
        with (
            patch.object(app_main, "NOTICE_SOURCES", configured),
            patch.object(app_main, "load_source_health_summary", return_value=health),
            patch.object(app_main, "load_public_opps", return_value=[]),
        ):
            response = app_main.app.test_client().get("/sources")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("2 official procurement sources monitored", html)
        self.assertIn("Zero County Procurement", html)
        self.assertIn("no matching opportunities are currently listed", html)
        self.assertIn("latest crawl returned 0", html)

    def test_precise_calendar_uses_utc_instant(self):
        opportunity = {
            "id": "timed-bid",
            "_canonical_notice": True,
            "title": "Timed bridge bid",
            "source_id": "state-one",
            "source_name": "Agency One",
            "source_tier": "state",
            "notice_type": "construction",
            "due_date_raw": "2099-08-25T20:00:00Z",
            "source_status": "open",
            "status": "open",
        }
        with patch.object(app_main, "load_public_opps", return_value=[opportunity]):
            response = app_main.app.test_client().get("/opportunities/timed-bid/calendar.ics")

        calendar = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("DTSTART:20990825T200000Z", calendar)
        self.assertNotIn("DTSTART;VALUE=DATE", calendar)


if __name__ == "__main__":
    unittest.main()
