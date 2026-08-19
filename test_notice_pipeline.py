import sys
import json
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


CRAWLERS = Path(__file__).resolve().parent / "crawlers"
sys.path.insert(0, str(CRAWLERS))

import notice_crawlers
import notice_runner
import notice_sources
import source_health
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
        self.assertIsNone(
            notice_crawlers._classify_transport_scope(
                "Steel for the Department of Transportation and Infrastructure"
            )
        )

    def test_opengov_parser_reads_public_project_state(self):
        payload = {
            "count": 2,
            "rows": [
                {
                    "id": 101,
                    "title": "County bridge reconstruction",
                    "summary": "<p>Replace the existing bridge deck.</p>",
                    "proposalDeadline": "2099-09-30T20:00:00.000Z",
                    "financialId": "IFB-101",
                    "department": {"name": "Public Works"},
                },
                {
                    "id": 102,
                    "title": "Office paper supplies",
                    "summary": "<p>General office supplies.</p>",
                    "proposalDeadline": "2099-10-01T20:00:00.000Z",
                    "financialId": "IFB-102",
                    "department": {"name": "Administration"},
                },
            ],
        }
        html = (
            '<script>window.__data={"govProjects":{"wrong":true},'
            '"publicProject":{"govProjects":' + json.dumps(payload) + '},'
            '"runtimeValue":undefined};</script>'
        )
        source = dict(SOURCE, parser="opengov", portal_code="testcounty")
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=html)):
            records = notice_crawlers.parse_opengov(source)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["contract_number"], "IFB-101")
        self.assertEqual(records[0]["due_date_raw"], "2099-09-30T20:00:00.000Z")
        self.assertTrue(records[0]["official_url"].endswith("/testcounty/projects/101"))

    def test_bidnet_parser_keeps_work_and_rejects_transportation_supplies(self):
        html = """
        <table>
          <tr class="mets-table-row">
            <td class="sol-num">B-100</td>
            <td class="sol-title"><a class="solicitation-link" href="/bridge">Bridge deck replacement</a></td>
            <td class="sol-publication-date"><span class="date-value">08/01/2099</span></td>
            <td class="sol-closing-date"><span class="date-value">09/01/2099</span></td>
          </tr>
          <tr class="mets-table-row">
            <td class="sol-num">B-200</td>
            <td class="sol-title"><a class="solicitation-link" href="/steel">Steel for Department of Transportation</a></td>
            <td class="sol-publication-date"><span class="date-value">08/01/2099</span></td>
            <td class="sol-closing-date"><span class="date-value">09/02/2099</span></td>
          </tr>
        </table>
        """
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=html)):
            records = notice_crawlers.parse_bidnet_agency(SOURCE)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["contract_number"], "B-100")
        self.assertEqual(records[0]["official_url"], "https://agency.example/bridge")

    def test_hudson_parser_uses_current_direct_rows(self):
        html = """
        <table>
          <tr><th>#</th><th>Title</th><th>Date Posted</th><th>Date Due</th><th>Commodities</th></tr>
          <tr onclick="document.location='index.php?section=view&amp;id=1'">
            <td>Bid-1</td><td>Central Avenue extension</td><td>08/01/2099</td><td>09/01/2099</td>
            <td>Construction or Related Services Engineering Services</td>
          </tr>
          <tr><td>Bid-2</td><td>Old bridge repair</td><td>01/01/2020</td><td>02/01/2020</td>
            <td>Construction or Related Services</td></tr>
        </table>
        """
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=html)):
            records = notice_crawlers.parse_hudson_county(SOURCE)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["contract_number"], "Bid-1")
        self.assertIn("index.php", records[0]["official_url"])

    def test_monmouth_parser_combines_construction_and_engineering_lists(self):
        def table(row=""):
            return SimpleNamespace(text=f"""
                <table><tr><th>Due Date</th><th>Request ID</th><th>Title</th></tr>{row}</table>
            """)

        responses = [
            table("<tr><td>09/01/2099</td><td>F-1</td><td>Bridge painting services</td><td><a href='/BidDetails?id=1'>View</a></td></tr>"),
            table("<tr><td>09/02/2099</td><td>P-1</td><td>Health insurance administration</td></tr>"),
            table("<tr><td>09/03/2099</td><td>P-2</td><td>Professional engineering services for roadway inspection</td><td><a href='/BidDetails?id=2'>View</a></td></tr>"),
        ]
        with patch.object(notice_crawlers, "_get", side_effect=responses):
            records = notice_crawlers.parse_monmouth_county(SOURCE)

        self.assertEqual({record["contract_number"] for record in records}, {"F-1", "P-2"})
        self.assertEqual(
            {record["notice_type"] for record in records},
            {"construction", "professional_services"},
        )

    def test_union_and_newark_water_parse_current_infrastructure_notices(self):
        union_html = """
        <h1>Invitations to Bid</h1>
        <p>East Coast Greenway Bikeway BA # 17-2099 Opening August 26, 2099 10:30 am Posted July 22, 2099</p>
        """
        water_html = """
        <ul><li class="list-item"><h2 class="list-item-content__title">Citywide Water/Wastewater Infrastructure Improvements</h2>
        <p>Project ID: 16-WS2099</p><p>Due Date: 08-27-2099</p><a href="/bid.pdf">View</a></li></ul>
        """
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=union_html)):
            union = notice_crawlers.parse_union_county(SOURCE)
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=water_html)):
            water = notice_crawlers.parse_newark_water(SOURCE)

        self.assertEqual(union[0]["contract_number"], "BA # 17-2099")
        self.assertEqual(water[0]["contract_number"], "16-WS2099")
        self.assertEqual(water[0]["official_url"], "https://agency.example/bid.pdf")

    def test_sos_directory_rejects_navigation_and_accepts_explicit_entity_table(self):
        navigation = """
        <div><a href="https://nj.gov/">NJ.gov</a></div>
        <li><a href="https://nj.gov/governor/">Governor</a></li>
        """
        directory = """
        <table>
          <tr><th>Public Entity</th><th>Legal Notice Website</th></tr>
          <tr><td>Example Township</td><td><a href="https://example.gov/notices">Notices</a></td></tr>
        </table>
        """
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=navigation)):
            self.assertEqual(notice_crawlers.parse_sos_directory(SOURCE), [])
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=directory)):
            entities = notice_crawlers.parse_sos_directory(SOURCE)

        self.assertEqual(len(entities), 1)
        self.assertEqual(entities[0]["entity_name"], "Example Township")
        self.assertEqual(entities[0]["legal_notices_url"], "https://example.gov/notices")

    def test_panynj_model_parser_keeps_nj_construction(self):
        source = notice_sources.SOURCES_BY_ID["state-panynj-construction"]
        payload = {
            "component": {
                "text": """
                    <table><tr><th>Contract Number</th><th>Due Date</th><th>Description</th></tr>
                    <tr><td><a href='/ewr.pdf'>EWR-100</a></td><td>20-Aug-2026</td>
                    <td><p>Newark Airport roadway rehabilitation</p></td></tr>
                    <tr><td><a href='/jfk.pdf'>JFK-200</a></td><td>21-Aug-2026</td>
                    <td><p>JFK Airport roadway rehabilitation</p></td></tr></table>
                """,
            }
        }
        response = SimpleNamespace(json=lambda: payload)
        with patch.object(notice_crawlers, "_get", return_value=response):
            records = notice_crawlers.parse_panynj(source)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["contract_number"], "EWR-100")
        self.assertEqual(records[0]["due_date_raw"], "20-Aug-2026")

    def test_drpa_parser_reads_detail_deadline(self):
        source = notice_sources.SOURCES_BY_ID["state-drpa-patco"]
        listing = SimpleNamespace(text="""
            <table><tr><td><h3>Request For Qualifications -- Construction Monitoring Services
            for Contract No. BF-65-2026 Benjamin Franklin Bridge Rehabilitation</h3>
            <a href='detail.asp'>[More]</a></td></tr></table>
        """)
        detail = SimpleNamespace(text="""
            <p>Statement of Qualification Due Date: August 28, 2026 2:00 PM EST</p>
        """)
        with patch.object(notice_crawlers, "_get", side_effect=[listing, detail]):
            records = notice_crawlers.parse_drpa(source)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["notice_type"], "professional_services")
        self.assertEqual(records[0]["due_date_raw"], "August 28, 2026")

    def test_njtpa_parser_keeps_active_rfps(self):
        source = notice_sources.SOURCES_BY_ID["state-njtpa"]
        response = SimpleNamespace(text="""
            <a class='rfp-item' href='/rfps/bridge-study/'>
              <h2 class='rfp-title'>County Bridge Local Concept Development Study</h2>
              <span class='rfp-status active'>Active</span>
              <div class='rfp-meta-item'><span class='label'>Deadline:</span>
                <time datetime='September 2, 2026 2:00 PM'>September 2, 2026</time></div>
            </a>
        """)
        with patch.object(notice_crawlers, "_get", return_value=response):
            records = notice_crawlers.parse_njtpa(source)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["notice_type"], "professional_services")
        self.assertEqual(records[0]["due_date_raw"], "September 2, 2026")

    def test_crawl_source_propagates_parser_failure(self):
        def fail(_source):
            raise RuntimeError("boom")

        with patch.dict(notice_crawlers.PARSER_MAP, {"broken": fail}):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                notice_crawlers.crawl_source(dict(SOURCE, parser="broken"), delay=0)


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

    def test_verified_empty_authoritative_source_retires_stale_records(self):
        source = dict(
            SOURCE,
            parser="opengov",
            allow_empty=True,
            empty_is_authoritative=True,
        )
        with (
            patch.object(notice_runner, "crawl_source", return_value=[]),
            patch.object(notice_runner, "_log_crawl"),
        ):
            fresh, refreshed = notice_runner.run_crawl([source])

        self.assertEqual(fresh, [])
        self.assertEqual(refreshed, {SOURCE["id"]})

    def test_sos_seed_replaces_invalid_stale_entities(self):
        saved = []
        with (
            patch.object(notice_runner, "parse_sos_directory", return_value=[]),
            patch.object(notice_runner, "_save", side_effect=lambda path, value: saved.append((path, value))),
            patch.object(notice_runner, "_log_crawl"),
        ):
            notice_runner.run_sos_seed()

        self.assertEqual(saved, [(notice_runner.SOS_ENT_F, [])])

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


class SourceHealthTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 16, 18, tzinfo=timezone.utc)
        self.source = {
            "id": "critical-source",
            "name": "Critical Source",
            "url": "https://agency.example/bids",
            "crawl_tier": 1,
            "source_tier": "state",
            "crawl_freq": "daily",
            "parser": "dedicated",
            "critical": True,
        }

    def test_missing_critical_source_is_an_error(self):
        health = source_health.evaluate_source(self.source, now=self.now)
        self.assertEqual(health["status"], "never_run")
        self.assertEqual(health["severity"], "error")

    def test_stale_source_is_detected(self):
        entry = {"last_crawl": (self.now - timedelta(hours=60)).isoformat(), "last_count": 5}
        health = source_health.evaluate_source(self.source, entry, self.now)
        self.assertEqual(health["status"], "stale")

    def test_large_count_drop_is_a_warning(self):
        history = [
            {"at": f"2026-08-{day:02d}T18:00:00+00:00", "count": count, "error": None}
            for day, count in ((12, 20), (13, 22), (14, 21), (16, 3))
        ]
        entry = {
            "last_crawl": history[-1]["at"],
            "last_count": 3,
            "last_error": None,
            "history": history,
        }
        health = source_health.evaluate_source(self.source, entry, self.now)
        self.assertEqual(health["status"], "count_drop")
        self.assertEqual(health["severity"], "warning")

    def test_allow_empty_reclassifies_stored_zero_record_error(self):
        source = dict(self.source, allow_empty=True)
        entry = {
            "last_crawl": self.now.isoformat(),
            "last_count": 0,
            "last_error": "zero_records",
            "history": [{"at": self.now.isoformat(), "count": 0, "error": "zero_records"}],
        }
        health = source_health.evaluate_source(source, entry, self.now)
        self.assertEqual(health["status"], "ok")
        self.assertEqual(health["severity"], "ok")
        self.assertIsNone(health["last_error"])
        self.assertEqual(health["consecutive_failures"], 0)

    def test_summary_includes_never_run_sources_and_county_coverage(self):
        summary = source_health.build_health_summary(notice_sources.NOTICE_SOURCES, [], self.now)
        self.assertEqual(summary["configured_sources"], len(notice_sources.NOTICE_SOURCES))
        self.assertEqual(summary["coverage"]["county_sources"], 21)
        self.assertEqual(summary["coverage"]["missing_counties"], [])


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
        self.assertRegex(
            response.get_data(as_text=True),
            r'<div class="num c-amber">\s*1\s*</div>\s*<div class="lbl">Official notices active</div>',
        )

    def test_public_notice_routes_use_canonical_notice_categories(self):
        construction = {
            "id": "construction-notice",
            "title": "County bridge reconstruction",
            "status": "open",
            "notice_type": "construction",
            "notice_subtype": "construction",
            "source_name": "County Purchasing",
            "source_tier": "county",
            "county": "Mercer",
            "due_date_parsed": "2099-12-31",
        }
        professional = {
            "id": "professional-notice",
            "title": "Bridge engineering services",
            "status": "open",
            "notice_type": "professional_services",
            "notice_subtype": "professional_services",
            "source_name": "County Purchasing",
            "source_tier": "county",
            "county": "Mercer",
            "due_date_parsed": "2099-12-31",
        }
        with (
            patch.object(notice_app, "_load_notices", return_value=[construction, professional]),
            patch.object(notice_app, "_load_crawl_log", return_value=[]),
        ):
            client = app_main.app.test_client()
            all_response = client.get("/notices")
            construction_response = client.get("/notices/construction")
            professional_response = client.get("/notices/professional-services")

        self.assertIn("County bridge reconstruction", all_response.get_data(as_text=True))
        self.assertIn("Bridge engineering services", all_response.get_data(as_text=True))
        self.assertIn("County bridge reconstruction", construction_response.get_data(as_text=True))
        self.assertNotIn("Bridge engineering services", construction_response.get_data(as_text=True))
        self.assertIn("Bridge engineering services", professional_response.get_data(as_text=True))
        self.assertNotIn("County bridge reconstruction", professional_response.get_data(as_text=True))


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
        self.assertIn("<loc>https://www.njtransportationbids.com/notices</loc>", xml)

    def test_open_gov_timestamp_deadline_is_parsed(self):
        self.assertEqual(
            app_main.parse_due("2026-08-25T20:00:47.395Z").isoformat(),
            "2026-08-25",
        )

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
