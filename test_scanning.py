import unittest
from copy import deepcopy
from datetime import date
from app.core.forecast import forecast_timing_note
from app.core.deadlines import normalize_deadline
from datetime import datetime, timezone
from unittest.mock import patch

from app import main, notice_routes
from app.core.scanning import closing_soon, first_seen_today, matches_search
from app.core.corridors import map_query, enrich_location
from crawlers import notice_runner
from crawlers import notice_crawlers
from crawlers.notice_sources import NOTICE_SOURCES
from openpyxl import Workbook
from types import SimpleNamespace
import io
import json


class ScanTrustTests(unittest.TestCase):
    def test_filter_removal_preserves_other_filters_and_feed_order(self):
        from bs4 import BeautifulSoup
        from urllib.parse import urlsplit, parse_qs
        for path in ('/notices', '/bids/construction', '/bids/professional-services'):
            response = main.app.test_client().get(path + '?q=bridge&county=Morris&sort=closing')
            self.assertEqual(response.status_code, 200)
            soup = BeautifulSoup(response.data, 'html.parser')
            link = soup.find('a', attrs={'aria-label': 'Remove County filter: Morris'})
            self.assertIsNotNone(link)
            self.assertEqual(parse_qs(urlsplit(link['href']).query), {'q': ['bridge'], 'sort': ['closing']})
            self.assertIsNotNone(soup.select_one('details.more-filters[open]'))
            self.assertIn('?sort=closing', soup.select_one('.filter-clear')['href'])

    def test_primary_status_controls_filter_typed_listings(self):
        rows = [dict(id=status, title='Bridge '+status, _canonical_notice=True,
                     source_name='Agency', notice_type='construction', status=status,
                     due_date_raw='09/01/2099' if status == 'open' else 'Fall 2099',
                     is_planned=status == 'upcoming') for status in ('open', 'upcoming')]
        for status in ('open', 'upcoming'):
            with (patch.object(main, 'load_public_opps', return_value=deepcopy(rows)),
                  patch.object(main, 'render_template', return_value='ok') as render):
                main.app.test_client().get('/bids/construction?status='+status)
            records = [r for g in render.call_args.kwargs['feed_groups'] for r in g['opportunities']]
            self.assertEqual([r['id'] for r in records], [status])

    def test_refresh_does_not_make_old_records_new(self):
        from app.core.freshness import stamp_refresh, newest_first
        old = dict(id='old', title='Bridge work', due_date_raw='09/20/2026',
                   first_seen_at='2026-08-01T12:00:00+00:00')
        same = dict(old)
        stamp_refresh(same, old, '2026-09-06T12:00:00+00:00')
        self.assertEqual(same['first_seen_at'], old['first_seen_at'])
        self.assertIsNone(same['materially_changed_at'])
        changed = dict(old, due_date_raw='09/25/2026')
        stamp_refresh(changed, old, '2026-09-06T12:00:00+00:00')
        self.assertEqual(changed['change_labels'], ['Deadline changed'])
        again = dict(changed)
        stamp_refresh(again, changed, '2026-09-07T12:00:00+00:00')
        self.assertEqual(again['materially_changed_at'], changed['materially_changed_at'])
        legacy = dict(id='legacy', title='A')
        refreshed_legacy = dict(legacy)
        stamp_refresh(refreshed_legacy, legacy, '2026-09-06T12:00:00+00:00')
        self.assertIsNone(refreshed_legacy['first_seen_at'])
        new = dict(id='new', first_seen_at='2026-09-01T12:00:00+00:00')
        self.assertEqual([r['id'] for r in newest_first([legacy, old, new])], ['new', 'old', 'legacy'])

    def test_freshness_groups_do_not_call_unknown_dates_new(self):
        from app.core.freshness import freshness_groups
        rows = [dict(id='unknown'), dict(id='new', first_seen_at='2026-09-06T12:00:00Z'),
                dict(id='old', first_seen_at='2026-08-01T12:00:00Z')]
        groups = freshness_groups(rows)
        self.assertEqual([r['id'] for r in groups[0]['opportunities']], ['new', 'old'])
        self.assertEqual(groups[1]['heading'], 'Discovery date not recorded')
        self.assertEqual(freshness_groups(rows, 'updated')[0]['heading'], 'No recorded changes')
        self.assertEqual(len(freshness_groups(rows, limit=1)[0]['opportunities']), 1)

    def test_merge_tracks_discovery_changes_and_amendments_separately(self):
        checked = '2026-09-06T12:00:00+00:00'
        row = dict(id='one', source_id='agency', contract_number='123', title='Bridge repair')
        with patch.object(notice_runner, '_now', return_value=checked):
            first = notice_runner._merge([], [dict(row)])[0]
            same = notice_runner._merge([dict(first)], [dict(row)])[0]
            amendment = dict(row, id='amended', title='Bridge repair revised')
            merged = notice_runner._merge([dict(same)], [amendment], {'agency'})
        self.assertEqual(first['first_seen_at'], checked)
        self.assertEqual(same['last_checked_at'], checked)
        self.assertIsNone(same['materially_changed_at'])
        amended = next(r for r in merged if r['id'] == 'amended')
        self.assertEqual(amended['first_seen_at'], checked)
        self.assertEqual(amended['change_labels'], ['Title changed'])

    def test_homepage_newest_is_not_deadline_order(self):
        rows = [dict(id=identity, title=identity, _canonical_notice=True,
                     source_id='test', source_name='Test agency', notice_type='construction',
                     status='open', due_date_raw=due, first_seen_at=seen)
                for identity, due, seen in (
                    ('Older sooner', '09/01/2099', '2026-08-01T12:00:00Z'),
                    ('New later', '10/01/2099', '2026-09-06T12:00:00Z'))]
        with (patch.object(main, 'load_public_opps', return_value=rows),
              patch.object(main, 'load_public_sources', return_value=[]),
              patch.object(main, 'render_template', return_value='ok') as render):
            main.app.test_client().get('/')
        self.assertEqual([r['id'] for r in render.call_args.kwargs['open_lane'][0]['opportunities']],
                         ['New later', 'Older sooner'])

    def test_feed_options_render_on_all_public_feeds(self):
        client = main.app.test_client()
        for path in ('/', '/notices', '/bids/construction', '/bids/professional-services'):
            for order in ('newest', 'updated', 'closing'):
                with self.subTest(path=path, order=order):
                    response = client.get(path + '?sort=' + order)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('name="sort"', response.get_data(as_text=True))

    def test_transit_reads_only_calendar_hydration_body(self):
        source = next(s for s in NOTICE_SOURCES if s['id'] == 'state-njtransit')
        body = '<table><tr><td>09/28/26</td><td>11:00</td><td>Proposals Due: RFP 123 "Bridge rehabilitation"</td><td>123</td></tr></table>'
        payload = [{'body': 1, 'slug': 2, 'title': 3}, body,
                   '/procurement/calendar', 'Procurement Calendar']
        with (patch.object(notice_crawlers, '_get', return_value=SimpleNamespace(
                text='<script id="__NUXT_DATA__" type="application/json">'+json.dumps(payload)+'</script>')),
              patch.object(notice_crawlers, 'date') as clock):
            clock.today.return_value = date(2026, 9, 6)
            self.assertEqual(len(notice_crawlers.parse_njtransit(source)), 1)
        payload[2] = '/unrelated'
        with patch.object(notice_crawlers, '_get', return_value=SimpleNamespace(
                text='<script id="__NUXT_DATA__">'+json.dumps(payload)+'</script>')):
            with self.assertRaises(RuntimeError):
                notice_crawlers.parse_njtransit(source)

    def test_transit_page_shell_is_not_a_successful_empty_refresh(self):
        with patch.object(notice_crawlers, '_get', return_value=SimpleNamespace(text='<h1>Procurement Calendar</h1>Loading...')):
            with self.assertRaisesRegex(RuntimeError, 'did not load'):
                notice_crawlers.parse_njtransit({'url': 'https://example.com'})

    def test_homepage_separates_elapsed_forecasts_without_dropping_them(self):
        rows = [dict(id=str(i), title=title, _canonical_notice=True, source_id='state-njdot-profserv-upcoming',
                     source_name='NJDOT', status='upcoming', is_planned=True,
                     notice_type='professional_services', due_date_raw=raw)
                for i, (title, raw) in enumerate([('Old forecast', 'Spring 2020'),
                                                 ('Future forecast', 'Fall 2099')])]
        with (patch.object(main, 'load_public_opps', return_value=rows),
              patch.object(main, 'load_public_sources', return_value=[]),
              patch.object(main, 'render_template', return_value='ok') as render):
            main.app.test_client().get('/')
        context = render.call_args.kwargs
        self.assertEqual([r['title'] for r in context['pipeline_preview']], ['Future forecast'])
        self.assertEqual([r['title'] for r in context['elapsed_forecasts']], ['Old forecast'])
        self.assertEqual(context['stats']['pipeline'], 2)

    def test_njdot_preserves_elapsed_visible_rows_not_hidden_history(self):
        book = Workbook()
        sheet = book.active
        sheet.append(['', '', 'Design', 'Visible bridge', 'Morris', 'Federal', 'Spring 2026'])
        sheet.append(['', '', 'Design', 'Hidden bridge', 'Morris', 'Federal', 'Summer 2024'])
        sheet.row_dimensions[2].hidden = True
        data = io.BytesIO()
        book.save(data)
        source = dict(next(s for s in NOTICE_SOURCES if s['id'] == 'state-njdot-profserv-upcoming'))
        with patch.object(notice_crawlers, '_get', side_effect=[
            SimpleNamespace(text='<a href="forecast.xlsx">Forecast</a>'),
            SimpleNamespace(text='<table></table>'), SimpleNamespace(content=data.getvalue())]):
            rows = notice_crawlers.parse_njdot_profserv_upcoming(source)
        self.assertEqual([r['title'] for r in rows], ['NJDOT upcoming: Visible bridge'])

    def test_transit_extracts_publication_date_without_inventing_deadline(self):
        source = next(s for s in NOTICE_SOURCES if s['id'] == 'state-njtransit')
        page = SimpleNamespace(extract_text=lambda: 'August 19, 2026\n\nExpected Advertisement: August\n\n'
            'Invitations for Bid\n\n\u2022 Bridge Rehabilitation of Raritan Valley Line over Roosevelt Avenue\n'
            'NJ TRANSIT is seeking bridge rehabilitation bids.')
        with (patch.object(notice_crawlers, '_get', return_value=SimpleNamespace(content=b'pdf')),
              patch.object(notice_crawlers, 'PdfReader', return_value=SimpleNamespace(pages=[page]))):
            rows = notice_crawlers._parse_njtransit_upcoming_pdf(source, 'https://example.com/forecast.pdf')
        self.assertEqual(rows[0]['forecast_publication_date'], '2026-08-19')
        self.assertEqual(rows[0]['due_date_raw'], 'August')

    def test_source_aware_forecast_aging_preserves_deadline_and_lifecycle(self):
        for raw, today, elapsed in (
            ('Summer 2026', date(2026, 9, 30), False),
            ('Summer 2026', date(2026, 10, 1), True),
            ('Summer 2026 (May/June)', date(2026, 9, 5), True),
            ('Fall 26', date(2026, 9, 5), False),
            ('Winter 26', date(2026, 9, 5), False),
        ):
            with self.subTest(raw=raw, today=today):
                r = normalize_deadline(dict(source_id='state-njdot-profserv-upcoming',
                    status='upcoming', due_date_raw=raw), today)
                self.assertEqual(r['forecast_window_elapsed'], elapsed)
                self.assertEqual(r['status'], 'upcoming')
                self.assertIsNone(r['due_date_parsed'])
                self.assertEqual(r['due_date_raw'], raw)

    def test_transit_forecast_requires_publication_evidence_not_refresh_time(self):
        record = dict(source_id='state-njtransit', status='upcoming',
                      due_date_raw='August', crawled_at='2026-09-05')
        self.assertFalse(normalize_deadline(dict(record), date(2026, 9, 5))['forecast_window_elapsed'])
        record['forecast_publication_date'] = '2026-08-19'
        r = normalize_deadline(dict(record), date(2026, 9, 5))
        self.assertTrue(r['forecast_window_elapsed'])
        self.assertIsNone(r['due_date_parsed'])
        record['due_date_raw'] = 'September/October'
        self.assertFalse(normalize_deadline(dict(record), date(2026, 10, 31))['forecast_window_elapsed'])
        self.assertTrue(normalize_deadline(dict(record), date(2026, 11, 1))['forecast_window_elapsed'])

    def test_forecast_timing_never_invents_dates_or_changes_status(self):
        today = date(2026, 9, 5)
        for raw in ('August', 'September/October'):
            record = dict(due_date_raw=raw, status='upcoming', crawled_at='2026-09-05')
            normalize_deadline(record, today)
            self.assertIn('year not stated', record['forecast_timing_note'])
            self.assertEqual(record['due_date_raw'], raw)
            self.assertEqual(record['status'], 'upcoming')
            self.assertIsNone(record['due_date_parsed'])
        for raw in ('August 2026', 'Summer 2025'):
            self.assertIn('has passed', forecast_timing_note(raw, today))
        self.assertIn('abbreviated forecast year', forecast_timing_note('Winter 27', today))
        for raw in ('Summer 2026', 'Winter 2026', 'September 2026', 'Fall 2026', 'December 2026/January 2027'):
            self.assertNotIn('has passed', forecast_timing_note(raw, today))
        record = normalize_deadline(dict(due_date_raw='09/10/2026'), today)
        self.assertIsNone(record['forecast_timing_note'])

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
