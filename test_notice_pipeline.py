import sys
import json
import re
import unittest
from datetime import date, datetime, timedelta, timezone
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

FIXTURES = Path(__file__).resolve().parent / "test_fixtures"


class NoticeCrawlerTests(unittest.TestCase):
    def test_akamai_denial_retries_with_browser_transport(self):
        denied = SimpleNamespace(
            status_code=403,
            headers={"Server": "AkamaiGHost"},
            text="<title>Access Denied</title>",
        )
        denied.raise_for_status = lambda: (_ for _ in ()).throw(
            notice_crawlers.requests.HTTPError(response=denied)
        )
        accepted = SimpleNamespace(
            status_code=200,
            headers={},
            text="<html>Official listing</html>",
            raise_for_status=lambda: None,
        )
        browser = SimpleNamespace(get=lambda *args, **kwargs: accepted)

        with (
            patch.object(notice_crawlers.requests, "get", return_value=denied),
            patch.object(notice_crawlers, "browser_requests", browser),
        ):
            response = notice_crawlers._get("https://county.example/bids")

        self.assertIs(response, accepted)

    def test_somerset_parser_reads_rows_and_preserves_source_fields(self):
        html = (FIXTURES / "somerset_list_bid.html").read_text(encoding="utf-8")
        source = dict(
            SOURCE,
            id="county-somerset",
            parser="somerset_county",
            listing_urls=[SOURCE["url"]],
        )
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=html)):
            records = notice_crawlers.parse_somerset_county(source)

        self.assertEqual(
            {record["contract_number"] for record in records},
            {"CC-0099-26", "CC-0054-26", "CC-0001-26"},
        )
        traffic = next(record for record in records if record["contract_number"] == "CC-0099-26")
        self.assertEqual(traffic["title"], "Traffic Control Signs, Supports & Hardware Devices")
        self.assertEqual(traffic["title_raw"], "Traffic Control Signs, Supports & Hardware Devices NEW!")
        self.assertEqual(traffic["due_date_raw"], "09/17/2099")
        self.assertEqual(traffic["source_status"], "Open")
        self.assertEqual(
            traffic["official_url"],
            "https://agency.example/Home/Components/RFP/RFP/4923/2046",
        )

        normalized = notice_runner._enrich(traffic)
        self.assertEqual(normalized["deadline_precision"], "date")
        self.assertIsNone(normalized["deadline_at"])
        self.assertIn("time not published", normalized["deadline_display"])

        expired = next(record for record in records if record["contract_number"] == "CC-0001-26")
        self.assertEqual(expired["source_status"], "Open")
        self.assertEqual(notice_runner._enrich(expired)["status"], "expired")

    def test_warren_empty_body_ignores_stale_metadata(self):
        html = (FIXTURES / "warren_rfp_empty.html").read_text(encoding="utf-8")
        source = dict(SOURCE, parser="warren_county")
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=html)):
            records = notice_crawlers.parse_warren_county(source)

        self.assertEqual(records, [])

    def test_salem_parser_reads_only_current_transportation_work(self):
        html = (FIXTURES / "salem_current_opportunities.html").read_text(encoding="utf-8")
        source = dict(
            SOURCE,
            id="county-salem",
            name="Salem County Purchasing",
            url="https://www.salempurchasing.org/",
            parser="salem_county",
        )
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=html)):
            records = notice_crawlers.parse_salem_county(source)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["contract_number"], "26-20")
        self.assertEqual(records[0]["notice_type"], "construction")
        self.assertEqual(records[0]["due_date_raw"], "08/25/2099")
        self.assertEqual(
            records[0]["official_url"],
            "https://www.salempurchasing.org/bids/view?rfp_session=signal",
        )

    def test_salem_source_uses_authoritative_daily_portal(self):
        source = notice_sources.SOURCES_BY_ID["county-salem"]
        self.assertEqual(source["url"], "https://www.salempurchasing.org/")
        self.assertEqual(source["parser"], "salem_county")
        self.assertEqual(source["crawl_freq"], "daily")
        self.assertTrue(source["empty_is_authoritative"])

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

    def test_njdot_construction_splits_nested_project_paragraphs(self):
        html = """
        <table>
          <tr><th>Letting Date</th><th>Project</th></tr>
          <tr><td>09/17/26</td><td><div>
            <p>Route 1 bridge in Mercer County, DP No: 26107.</p>
            <p>Route 33 paving in Monmouth County, DP No: 26118.</p>
          </div></td></tr>
        </table>
        """
        response = SimpleNamespace(text=html)
        with patch.object(notice_crawlers, "_get", return_value=response):
            records = notice_crawlers.parse_njdot_construction(SOURCE)

        self.assertEqual(len(records), 2)
        self.assertEqual({record["contract_number"] for record in records}, {"DP-26107", "DP-26118"})
        self.assertTrue(all(record["title"].count("DP No") == 1 for record in records))

    def test_geography_segmentation_failure_enters_review_state(self):
        record = notice_crawlers._base_record(
            SOURCE,
            "Mercer County bridge DP No: 26107. Essex County paving DP No: 26118.",
            SOURCE["url"],
            "construction",
        )
        enriched = notice_runner._enrich(record)

        self.assertEqual(enriched["status"], "review_required")
        self.assertEqual(enriched["counties"], [])
        self.assertTrue(enriched["geography_review_required"])

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
        self.assertEqual(
            notice_crawlers._classify_transport_scope("Snow plowing for county roads"),
            "construction",
        )
        self.assertEqual(
            notice_crawlers._classify_transport_scope("Bulk rock salt purchase and delivery"),
            "construction",
        )
        self.assertEqual(
            notice_crawlers._classify_transport_scope("Snow plow parts and supplies"),
            "construction",
        )
        self.assertIsNone(
            notice_crawlers._classify_transport_scope("Heavy duty vehicle collision repair")
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

    def test_bidexpress_agency_reads_only_upcoming_transportation_work(self):
        html = """
        <h2>Upcoming Solicitations</h2>
        <table>
          <tr><th>Number</th><th>Deadline</th></tr>
          <tr><td><a href="/solicitations/100">BID # 209901 Road resurfacing program</a></td>
              <td>09/01/2099 03:00 PM UTC</td></tr>
          <tr><td><a href="/solicitations/200">RFP # 209902 Legal services</a></td>
              <td>09/02/2099 03:00 PM UTC</td></tr>
        </table>
        <h2>Closed Solicitations</h2>
        <table><tr><td><a href="/solicitations/300">BID # 209800 Bridge repair</a></td>
                   <td>01/01/2098 03:00 PM UTC</td></tr></table>
        """
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=html)):
            records = notice_crawlers.parse_bidexpress_agency(SOURCE)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["contract_number"], "BID # 209901")
        self.assertEqual(records[0]["official_url"], "https://agency.example/solicitations/100")

    def test_passaic_parser_reads_only_current_transportation_work(self):
        html = """
        <h2>Current Opportunities</h2>
        <table>
          <tr><th>#</th><th>Title</th><th>Date Issued</th><th>Due Date</th></tr>
          <tr><td><a href="/bids/view?id=1">SB-99-001</a></td>
              <td>Snow Plowing for Passaic County Roads</td><td>08/01/2099</td><td>09/01/2099</td></tr>
          <tr><td><a href="/bids/view?id=2">RFQ-99-002</a></td>
              <td>Outside legal counsel</td><td>08/01/2099</td><td>09/02/2099</td></tr>
        </table>
        <h2>Pending Award Opportunities</h2>
        <table><tr><td><a href="/bids/view?id=3">RFP-99-003</a></td>
                   <td>Bridge inspection services</td><td>07/01/2099</td><td>08/01/2099</td></tr></table>
        """
        with patch.object(notice_crawlers, "_get", return_value=SimpleNamespace(text=html)):
            records = notice_crawlers.parse_passaic_bids(SOURCE)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["contract_number"], "SB-99-001")
        self.assertEqual(records[0]["notice_type"], "construction")
        self.assertEqual(records[0]["official_url"], "https://agency.example/bids/view?id=1")

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
                    <tr><td><a href='/ewr.pdf'>EWR-100</a></td><td>20-Aug-2099</td>
                    <td><p>Newark Airport roadway rehabilitation</p></td></tr>
                    <tr><td><a href='/jfk.pdf'>JFK-200</a></td><td>21-Aug-2099</td>
                    <td><p>JFK Airport roadway rehabilitation</p></td></tr></table>
                """,
            }
        }
        response = SimpleNamespace(json=lambda: payload)
        with patch.object(notice_crawlers, "_get", return_value=response):
            records = notice_crawlers.parse_panynj(source)

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["contract_number"], "EWR-100")
        self.assertEqual(records[0]["due_date_raw"], "20-Aug-2099")

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
    def test_runner_enriches_timed_deadline_without_legacy_date_state(self):
        record = {
            "id": "timed-record",
            "title": "Bridge construction bid",
            "due_date_raw": "2099-08-25T20:00:00Z",
            "source_status": "open",
        }

        enriched = notice_runner._enrich(record)

        self.assertEqual(enriched["status"], "open")
        self.assertEqual(enriched["deadline_at"], "2099-08-25T20:00:00Z")
        self.assertFalse(enriched["urgent"])

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

    def test_inaccessible_source_is_not_crawled_or_logged_as_failure(self):
        source = dict(
            SOURCE,
            parser="questcdn",
            crawl_state="inaccessible",
            access_reason="Project search requires a paid membership.",
        )
        with (
            patch.object(notice_runner, "crawl_source") as crawl,
            patch.object(notice_runner, "_log_crawl") as log_crawl,
        ):
            fresh, refreshed = notice_runner.run_crawl([source])

        self.assertEqual(fresh, [])
        self.assertEqual(refreshed, set())
        crawl.assert_not_called()
        log_crawl.assert_called_once_with(
            SOURCE["id"],
            0,
            state="inaccessible",
            message="Project search requires a paid membership.",
        )

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

    def test_inaccessible_source_is_a_disclosed_warning_not_a_failure(self):
        source = dict(
            self.source,
            critical=False,
            crawl_state="inaccessible",
            access_reason="Anonymous search is registration-gated.",
        )
        health = source_health.evaluate_source(source, now=self.now)

        self.assertEqual(health["status"], "inaccessible")
        self.assertEqual(health["severity"], "warning")
        self.assertEqual(health["message"], "Anonymous search is registration-gated.")

    def test_summary_includes_never_run_sources_and_county_coverage(self):
        summary = source_health.build_health_summary(notice_sources.NOTICE_SOURCES, [], self.now)
        self.assertEqual(summary["configured_sources"], len(notice_sources.NOTICE_SOURCES))
        self.assertEqual(summary["coverage"]["county_sources"], 21)
        self.assertEqual(summary["coverage"]["missing_counties"], [])

    def test_summary_surfaces_active_segmentation_review_records(self):
        notices = [
            {
                "source_id": self.source["id"],
                "geography_review_required": True,
                "source_inactive": False,
            },
            {
                "source_id": self.source["id"],
                "geography_review_required": True,
                "source_inactive": True,
            },
        ]
        crawl_log = [{
            "source_id": self.source["id"],
            "last_crawl": self.now.isoformat(),
            "last_count": 1,
            "last_error": None,
            "history": [{"at": self.now.isoformat(), "count": 1, "error": None}],
        }]
        summary = source_health.build_health_summary([self.source], crawl_log, self.now, notices)

        self.assertEqual(summary["overall"], "warning")
        self.assertEqual(summary["data_quality"]["active_records_requiring_segmentation_review"], 1)
        self.assertEqual(
            summary["data_quality"]["segmentation_review_by_source"],
            {self.source["id"]: 1},
        )


class PublicDashboardTests(unittest.TestCase):
    @staticmethod
    def _scan_record(record_id, title, due_date_raw="", status="open", **overrides):
        record = {
            "id": record_id,
            "_canonical_notice": True,
            "title": title,
            "source_id": "county-test",
            "source_name": "Test County Purchasing",
            "source_tier": "county",
            "source_url": "https://agency.example/bids",
            "official_url": f"https://agency.example/bids/{record_id}",
            "county": "Statewide",
            "notice_type": "construction",
            "notice_subtype": "construction",
            "due_date_raw": due_date_raw,
            "contract_number": f"TEST-{record_id}",
            "access_type": "Public access",
            "platform": "Agency website",
            "status": status,
            "source_status": status,
            "crawled_at": "2026-08-21T12:00:00+00:00",
        }
        record.update(overrides)
        return record

    def test_opportunity_scan_defaults_to_live_deadline_order(self):
        records = [
            self._scan_record("later", "Bridge work closing later", "09/20/2026"),
            self._scan_record("soon", "Somerset CC-0043-26 closing soon", "08/24/2026"),
            self._scan_record("month", "Road work closing this month", "08/31/2026"),
            self._scan_record("planned", "Planned intersection improvements", status="upcoming", is_planned=True),
            self._scan_record("nodate", "Current drainage work without deadline", source_status="open"),
            self._scan_record("expired", "Expired paving contract", "08/01/2026", status="expired"),
            self._scan_record("noise", "Excluded navigation noise", noise_flagged=True),
        ]

        class FixedDate(date):
            @classmethod
            def today(cls):
                return cls(2026, 8, 21)

        with (
            patch.object(app_main, "load_public_opps", return_value=records),
            patch.object(app_main, "date", FixedDate),
        ):
            response = app_main.app.test_client().get("/bids/construction")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("Expired paving contract", html)
        self.assertNotIn("Excluded navigation noise", html)
        self.assertLess(html.index("closing soon"), html.index("closing later"))
        self.assertIn("Closing within 7 days", html)
        self.assertIn("Closing this month", html)
        self.assertIn("Upcoming or planned", html)
        self.assertIn("Deadline not resolved", html)
        self.assertIn("Mon, Aug 24, 2026 (time not published)", html)
        self.assertNotIn("12:00 AM", html)

    def test_show_closed_includes_expired_and_noise_without_changing_data(self):
        records = [
            self._scan_record("live", "Live bridge contract", "09/20/2099"),
            self._scan_record("expired", "Expired paving contract", "08/01/2020", status="expired"),
            self._scan_record("noise", "Excluded navigation noise", noise_flagged=True),
        ]
        with patch.object(app_main, "load_public_opps", return_value=records):
            response = app_main.app.test_client().get("/bids/construction?show_closed=1")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Live bridge contract", html)
        self.assertIn("Expired paving contract", html)
        self.assertIn("Excluded navigation noise", html)
        self.assertIn("Closed and excluded", html)
        self.assertIn('name="show_closed" value="1"', html)

    def test_scan_card_uses_normalized_geography_and_official_handoff(self):
        explicit = self._scan_record(
            "explicit",
            "Bridge reconstruction in Mercer County",
            "09/20/2099",
        )
        unresolved = self._scan_record(
            "unresolved",
            "County road resurfacing program",
            "09/21/2099",
            county="Salem",
            county_provenance="AGENCY_JURISDICTION",
        )
        with patch.object(app_main, "load_public_opps", return_value=[explicit, unresolved]):
            response = app_main.app.test_client().get("/bids/construction")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Mercer County", html)
        self.assertIn("County not stated in notice", html)
        self.assertIn("Contract TEST-explicit", html)
        self.assertIn(
            'href="https://agency.example/bids/explicit" target="_blank" rel="noopener"',
            html,
        )
        self.assertIn("View official notice", html)

    def test_homepage_counts_canonical_crawler_sources(self):
        enriched = {
            "id": "one",
            "title": "One live construction opportunity",
            "source_name": "Agency One",
            "status": "open",
            "record_type": "construction",
            "due_date_parsed": None,
            "deadline_display": "Date not published",
            "county_display": "County not stated in notice",
        }
        with (
            patch.object(app_main, "load_public_opps", return_value=[{"id": "one"}]),
            patch.object(
                app_main,
                "load_public_sources",
                return_value=[
                    {"id": "healthy-agency", "severity": "ok"},
                    {"id": "limited-agency", "severity": "warning"},
                ],
            ),
            patch.object(app_main, "enrich", return_value=enriched),
        ):
            response = app_main.app.test_client().get("/")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("1 active opportunity", html)
        self.assertIn("2 configured sources", html)
        self.assertIn("1 healthy", html)
        self.assertIn('class="nav-toggle"', html)
        self.assertIn('id="primary-navigation"', html)

    def test_homepage_uses_normalized_deadlines_and_shared_live_status(self):
        records = [
            self._scan_record(
                "notice-25be67d23f9a",
                "Construction Project Management for Various Road and Bridge Projects in Ocean County",
                "2026-08-25T20:00:00.000Z",
                county="Ocean",
                platform="OpenGov",
            ),
            self._scan_record(
                "notice-6ebfc6cc572a",
                "MILLING & RESURFACING SPRING VALLEY ROAD (C.R. 601)",
                "08/25/2026",
                county="Morris",
                source_name="Morris County Bids",
                source_id="county-morris",
            ),
            self._scan_record(
                "passed",
                "PANYNJ GWB-244.306 expired bridge work",
                "08/20/2026",
                source_name="Port Authority NY/NJ",
                source_id="state-panynj",
            ),
        ]

        class FixedDate(date):
            @classmethod
            def today(cls):
                return cls(2026, 8, 21)

        with (
            patch.object(app_main, "load_public_opps", return_value=records),
            patch.object(app_main, "load_public_sources", return_value=[]),
            patch.object(app_main, "date", FixedDate),
        ):
            client = app_main.app.test_client()
            response = client.get("/")
            detail = client.get("/opportunities/notice-6ebfc6cc572a")

        html = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Construction", html)
        self.assertIn("Professional services", html)
        self.assertIn("Tue, Aug 25, 2026 at 4:00 PM ET", html)
        self.assertIn("Tue, Aug 25, 2026 (time not published)", html)
        self.assertNotRegex(html, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")
        self.assertNotIn("12:00 AM", html)
        self.assertNotIn("expired bridge work", html)
        self.assertNotIn("not resolved", html.lower())
        self.assertIn("County not stated in notice", html)
        self.assertIn("OpenGov", html)
        self.assertNotIn("not resolved", detail.get_data(as_text=True).lower())
        self.assertIn("County not stated in notice", detail.get_data(as_text=True))

    def test_homepage_uses_canonical_lanes_and_an_unclassified_fallback(self):
        records = [
            self._scan_record(
                "construction",
                "Route resurfacing due tomorrow",
                "08/22/2026 11:00 PM ET",
            ),
            self._scan_record(
                "professional",
                "Bridge design services",
                "08/23/2026",
                notice_type="professional_services",
                notice_subtype="professional_services",
                platform="BidNet Direct",
            ),
            self._scan_record(
                "unknown",
                "NJTA opportunity awaiting type review",
                "08/24/2026",
                source_id="state-njta",
                source_name="New Jersey Turnpike Authority",
                notice_type="uncategorized",
                notice_subtype=None,
            ),
            self._scan_record("expired", "Expired construction work", "08/20/2026"),
        ]

        class FixedDate(date):
            @classmethod
            def today(cls):
                return cls(2026, 8, 21)

        with (
            patch.object(app_main, "load_public_opps", return_value=records),
            patch.object(app_main, "load_public_sources", return_value=[]),
            patch.object(app_main, "date", FixedDate),
        ):
            response = app_main.app.test_client().get("/")

        html = response.get_data(as_text=True)
        construction_lane = re.search(
            r'<section class="opportunity-lane lane-construction".*?</section>', html, re.S
        ).group(0)
        professional_lane = re.search(
            r'<section class="opportunity-lane lane-professional".*?</section>', html, re.S
        ).group(0)
        unclassified_lane = re.search(
            r'<section class="opportunity-lane lane-unclassified".*?</section>', html, re.S
        ).group(0)

        self.assertIn("Route resurfacing due tomorrow", construction_lane)
        self.assertNotIn("Bridge design services", construction_lane)
        self.assertIn("Bridge design services", professional_lane)
        self.assertNotIn("NJTA opportunity awaiting type review", professional_lane)
        self.assertIn("NJTA opportunity awaiting type review", unclassified_lane)
        self.assertIn("1 day", construction_lane)
        self.assertIn("time not published", professional_lane)
        self.assertIn("BidNet Direct", professional_lane)
        self.assertNotIn("Agency website", construction_lane)
        self.assertNotIn("Expired construction work", html)

    def test_homepage_prioritizes_opportunities_and_resources_move_off_page(self):
        with (
            patch.object(app_main, "load_public_opps", return_value=[]),
            patch.object(app_main, "load_public_sources", return_value=[]),
        ):
            client = app_main.app.test_client()
            home = client.get("/")
            resources = client.get("/resources")

        home_html = home.get_data(as_text=True)
        resources_html = resources.get_data(as_text=True)
        self.assertEqual(resources.status_code, 200)
        self.assertNotIn("Bidding Platforms", home_html)
        self.assertNotIn("https://www.bidexpress.com", home_html)
        self.assertNotIn('class="board-grid"', home_html)
        self.assertIn("Contractor network", home_html)
        self.assertIn("NJDOT Standard Specifications", resources_html)
        self.assertIn("Federal wage determinations", resources_html)
        self.assertIn("NJDOT Prequalification", resources_html)
        self.assertIn('href="/resources"', home_html)

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
        upcoming = dict(
            self.active,
            id="upcoming-bid",
            title="Planned Route 9 drainage improvements",
            status="upcoming",
            is_planned=True,
        )
        noise = dict(self.active, id="noise-bid", noise_flagged=True)
        client = app_main.app.test_client()
        robots = client.get("/robots.txt")
        self.assertEqual(robots.status_code, 200)
        self.assertIn("Sitemap: https://www.njtransportationbids.com/sitemap.xml", robots.get_data(as_text=True))
        self.assertIn("Disallow: /*?", robots.get_data(as_text=True))

        with patch.object(
            app_main,
            "load_public_opps",
            return_value=[self.active, upcoming, expired, noise],
        ):
            sitemap = client.get("/sitemap.xml")

        xml = sitemap.get_data(as_text=True)
        self.assertEqual(sitemap.status_code, 200)
        self.assertIn("/opportunities/active-bid", xml)
        self.assertIn("/opportunities/upcoming-bid", xml)
        self.assertNotIn("/opportunities/expired-bid", xml)
        self.assertNotIn("/opportunities/noise-bid", xml)
        self.assertIn("<loc>https://www.njtransportationbids.com/notices</loc>", xml)
        self.assertIn("<loc>https://www.njtransportationbids.com/resources</loc>", xml)

    def test_detail_pages_emit_unique_evidence_safe_search_metadata(self):
        route_one = dict(
            self.active,
            id="notice-09a31913dc62",
            title=(
                "Route 1, NB Bridge over Raritan River, Contract # 027153030, "
                "Reconstruction, Township of Edison, City of New Brunswick, "
                "County of Middlesex; DP No: 26107."
            ),
            notice_excerpt="Route 1 bridge work in Middlesex County.",
            county="Statewide",
            contract_number="027153030",
            due_date_raw="12/31/68",
        )
        route_nine = dict(
            self.active,
            id="route-nine",
            title="Route 9 drainage rehabilitation",
            notice_excerpt="Route 9 drainage work.",
            contract_number="009998877",
            due_date_raw="12/30/68 2:00 PM ET",
        )
        client = app_main.app.test_client()
        with patch.object(app_main, "load_public_opps", return_value=[route_one, route_nine]):
            first = client.get("/opportunities/notice-09a31913dc62?utm_source=test")
            second = client.get("/opportunities/route-nine")

        first_html = first.get_data(as_text=True)
        second_html = second.get_data(as_text=True)
        first_title = re.search(r"<title>(.*?)</title>", first_html, re.S).group(1).strip()
        second_title = re.search(r"<title>(.*?)</title>", second_html, re.S).group(1).strip()
        first_description = re.search(
            r'<meta name="description" content="([^"]*)">', first_html
        ).group(1)
        second_description = re.search(
            r'<meta name="description" content="([^"]*)">', second_html
        ).group(1)

        self.assertNotEqual(first_title, second_title)
        self.assertNotEqual(first_description, second_description)
        self.assertIn("Route 1", first_title)
        self.assertIn("027153030", first_title)
        self.assertIn("Middlesex", first_title)
        self.assertIn("DP 26107", first_title)
        self.assertIn("time not published", first_description)
        self.assertNotRegex(first_title + first_description, r"\b\d{1,2}:\d{2}\b|\b(?:AM|PM)\b")
        self.assertIn(
            'rel="canonical" href="https://www.njtransportationbids.com/opportunities/notice-09a31913dc62"',
            first_html,
        )
        self.assertIn(route_one["title"], first_html)

    def test_detail_metadata_omits_county_without_normalized_evidence(self):
        unsupported = dict(
            self.active,
            id="unsupported-county",
            title="Parts and Accessories for Snow Plows and Salt Spreaders",
            notice_excerpt="Road department equipment parts.",
            source_id="county-somerset",
            source_name="Somerset County Purchasing",
            county="Somerset",
            contract_number="CC-0043-26",
        )
        with patch.object(app_main, "load_public_opps", return_value=[unsupported]):
            response = app_main.app.test_client().get("/opportunities/unsupported-county")

        html = response.get_data(as_text=True)
        page_title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
        description = re.search(r'<meta name="description" content="([^"]*)">', html).group(1)
        self.assertNotIn("Somerset", page_title)
        self.assertNotIn("Somerset", description)
        self.assertIn("CC-0043-26", page_title)

    def test_home_and_construction_metadata_target_procurement_intent(self):
        client = app_main.app.test_client()
        with patch.object(app_main, "load_public_opps", return_value=[self.active]):
            home = client.get("/").get_data(as_text=True)
            construction = client.get("/bids/construction").get_data(as_text=True)

        self.assertRegex(home, r"<title>[^<]*NJDOT[^<]*</title>")
        self.assertRegex(construction, r"<title>[^<]*NJDOT[^<]*Construction Bids[^<]*</title>")

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
