import sys
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


CRAWLERS = Path(__file__).resolve().parent / "crawlers"
sys.path.insert(0, str(CRAWLERS))

import notice_crawlers
import notice_runner
import notice_sources
from app import main as app_main
from app import notice_routes as notice_app


SOURCE = {
    "id": "test-source",
    "name": "Test Transportation Agency",
    "source_tier": "state",
    "url": "https://agency.example/bids/",
    "county": "Statewide",
    "entity_type": "State Agency",
    "access_type": "Public access",
    "platform": "Agency website",
}


class NoticeCrawlerTests(unittest.TestCase):
    def test_njdot_construction_uses_live_dot_host(self):
        source = notice_sources.SOURCES_BY_ID["state-njdot-construction"]
        self.assertEqual(
            source["url"],
            "https://dot.nj.gov/transportation/business/procurement/ConstrServ/curradvproj.shtm",
        )

    def test_njdot_construction_keeps_latest_amended_contract_row(self):
        html = """
        <table>
          <tr><th>Letting Date</th><th>Project</th></tr>
          <tr><td>08/25/26</td><td><p>Route 1 bridge, Contract # 027153030, DP No: 26107.</p></td></tr>
          <tr><td>08/27/26</td><td><p>Route 33 paving, Contract No. 017254210, DP No: 26118.</p></td></tr>
          <tr><td>09/10/26</td><td><p>Drainage restoration on I-278, DP No: 26420.</p></td></tr>
          <tr><td>09/17/26</td><td><p><a href="notice-26107.pdf">Route 1 bridge, Contract # 027153030, DP No: 26107.</a></p></td></tr>
        </table>
        """
        response = SimpleNamespace(text=html)
        with patch.object(notice_crawlers, "_get", return_value=response):
            records = notice_crawlers.parse_njdot_construction(SOURCE)

        self.assertEqual(len(records), 3)
        route_one = next(record for record in records if record["contract_number"] == "027153030")
        self.assertEqual(route_one["due_date_raw"], "09/17/26")
        self.assertEqual(route_one["official_url"], "https://agency.example/bids/notice-26107.pdf")
        drainage = next(record for record in records if record["contract_number"] == "DP-26420")
        self.assertIn("I-278", drainage["title"])

    def test_njdot_professional_services_uses_due_date_column(self):
        html = """
        <table>
          <tr><th>TP Number</th><th>Posting Date</th><th>Project Type</th>
              <th>Project Description</th><th>Status</th><th>Due Date</th></tr>
          <tr><td>TP-999</td><td>8/1/26</td><td>Design B-1 Level A</td>
              <td>Bridge design services</td><td>Advertised</td><td>9/30/2026</td></tr>
        </table>
        """
        response = SimpleNamespace(text=html)
        with patch.object(notice_crawlers, "_get", return_value=response):
            records = notice_crawlers.parse_njdot_profserv(SOURCE)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["posting_date_raw"], "8/1/26")
        self.assertEqual(records[0]["due_date_raw"], "9/30/2026")
        self.assertEqual(records[0]["source_status"], "Advertised")

    def test_njtransit_keeps_transport_work_and_rejects_general_goods(self):
        html = """
        <table>
          <tr><th>Event Date</th><th>Time</th><th>Description</th><th>IFB/RFP No</th></tr>
          <tr><td>12/31/68</td><td>11:00</td>
              <td>Proposals Due: RFP No. 100, "Bridge Engineering Services."</td>
              <td>RFP No. 100</td></tr>
          <tr><td>12/31/68</td><td>11:00</td>
              <td>Electronic Bids Due for IFB No. 200, "Ticket Stock."</td>
              <td>IFB No. 200</td></tr>
        </table>
        """
        response = SimpleNamespace(text=html)
        with patch.object(notice_crawlers, "_get", return_value=response):
            records = notice_crawlers.parse_njtransit(SOURCE)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["notice_type"], "professional_services")
        self.assertIn("Bridge Engineering Services", records[0]["title"])

    def test_generic_procurement_words_are_not_transportation_scope(self):
        self.assertIsNone(notice_crawlers._classify_transport_scope("RFP for legal services"))
        self.assertIsNone(notice_crawlers._classify_transport_scope("Demolition of a building on Broadway"))
        self.assertEqual(
            notice_crawlers._classify_transport_scope("RFP for bridge inspection services"),
            "professional_services",
        )


class NoticeLifecycleTests(unittest.TestCase):
    def test_planned_notice_is_upcoming(self):
        record = {"title": "Future bridge design", "is_planned": True, "due_date_raw": "Fall 2099"}
        self.assertEqual(notice_runner._enrich(record)["status"], "upcoming")

    def test_authoritative_refresh_retires_missing_record(self):
        existing = [{"id": "old", "source_id": "agency", "title": "Old bid"}]
        merged = notice_runner._merge(existing, [], {"agency"})
        self.assertTrue(merged[0]["source_inactive"])
        self.assertEqual(notice_runner._enrich(merged[0])["status"], "expired")

    def test_failed_refresh_does_not_retire_existing_record(self):
        existing = [{"id": "old", "source_id": "agency", "title": "Old bid"}]
        merged = notice_runner._merge(existing, [], set())
        self.assertFalse(merged[0].get("source_inactive", False))

    def test_dedupe_prefers_fresh_active_contract_record(self):
        records = [
            {
                "id": "old",
                "source_id": "agency",
                "contract_number": "P100",
                "title": "Old title",
                "source_inactive": True,
                "crawled_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "id": "new",
                "source_id": "agency",
                "contract_number": "P100",
                "title": "Improved title",
                "source_inactive": False,
                "crawled_at": "2026-08-16T00:00:00+00:00",
            },
        ]
        deduped = notice_runner._dedupe(records)
        self.assertEqual([record["id"] for record in deduped], ["new"])


class PublicDashboardTests(unittest.TestCase):
    def test_homepage_counts_canonical_crawler_sources(self):
        enriched = {
            "status": "open",
            "record_type": "construction",
            "due_date_parsed": None,
        }
        with (
            patch.object(app_main, "load_public_opps", return_value=[{"id": "one"}]),
            patch.object(app_main, "load_public_sources", return_value=[{"id": "agency"}]),
            patch.object(app_main, "enrich", return_value=enriched),
        ):
            response = app_main.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.get_data(as_text=True),
            r'<div class="num">\s*1\s*</div>\s*<div class="lbl">Sources monitored</div>',
        )
        self.assertIn('class="nav-toggle"', response.get_data(as_text=True))
        self.assertIn('id="primary-navigation"', response.get_data(as_text=True))


class PublicSeoTests(unittest.TestCase):
    def setUp(self):
        self.active = {
            "id": "active-bid",
            "_canonical_notice": True,
            "title": "Route 1 bridge reconstruction",
            "notice_excerpt": "NJDOT bridge reconstruction contract in Middlesex County.",
            "source_id": "state-njdot-construction",
            "source_name": "NJDOT Construction Services",
            "source_tier": "state",
            "source_url": "https://dot.nj.gov/bids",
            "official_url": "https://dot.nj.gov/notice.pdf",
            "county": "Middlesex",
            "notice_type": "construction",
            "notice_subtype": "construction",
            "due_date_raw": "12/31/68",
            "contract_number": "DP-12345",
            "access_type": "Public access",
            "platform": "NJDOT website",
            "status": "open",
            "source_status": "open",
            "crawled_at": "2068-11-01T12:00:00+00:00",
        }

    def test_robots_and_sitemap_publish_canonical_active_urls(self):
        expired = dict(self.active, id="expired-bid", due_date_raw="01/01/20", status="expired")
        client = app_main.app.test_client()
        robots = client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn("Sitemap: https://www.njtransportationbids.com/sitemap.xml", robots.get_data(as_text=True))
        self.assertIn("Disallow: /*?", robots.get_data(as_text=True))

        with patch.object(app_main, "load_public_opps", return_value=[self.active, expired]):
            sitemap = client.get("/sitemap.xml")

        xml = sitemap.get_data(as_text=True)
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("/opportunities/active-bid", xml)
        self.assertNotIn("/opportunities/expired-bid", xml)
        self.assertNotIn("<loc>https://www.njtransportationbids.com/notices</loc>", xml)

    def test_google_verification_file_is_served_at_site_root(self):
        response = app_main.app.test_client().get("/google0a60cf7052b4fd95.html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_data(as_text=True).strip(),
            "google-site-verification: google0a60cf7052b4fd95.html",
        )

    def test_detail_metadata_structured_data_and_calendar(self):
        client = app_main.app.test_client()
        with patch.object(app_main, "load_public_opps", return_value=[self.active]):
            response = client.get("/opportunities/active-bid")
            calendar = client.get("/opportunities/active-bid/calendar.ics")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn('rel="canonical" href="https://www.njtransportationbids.com/opportunities/active-bid"', html)
        self.assertIn("Official-source record", html)
        self.assertIn("Add deadline to calendar", html)
        scripts = re.findall(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', html, re.S)
        self.assertTrue(scripts)
        for script in scripts:
            json.loads(script)
        self.assertEqual(calendar.status_code, 200)
        self.assertIn("BEGIN:VCALENDAR", calendar.get_data(as_text=True))

    def test_notice_detail_redirects_to_canonical_opportunity(self):
        with patch.object(notice_app, "_load_notices", return_value=[self.active]):
            response = app_main.app.test_client().get("/notices/active-bid")

        self.assertEqual(response.status_code, 301)
        self.assertTrue(response.headers["Location"].endswith("/opportunities/active-bid"))


if __name__ == "__main__":
    unittest.main()
