"""Contractor-facing regressions from the October 28 Muse review."""
import csv
from contextlib import ExitStack
from datetime import datetime
from io import StringIO
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit, urlencode

from bs4 import BeautifulSoup
from app import main, notice_routes
from app.core.deadlines import EASTERN, apply_public_status, deadline_is_past, normalize_deadline, reconcile_authoritative_open_deadline
from app.core.work_focus import work_focus
from crawlers import notice_runner


NOW = datetime(2026, 10, 28, 12, tzinfo=EASTERN)


def notice(key='bid', **updates):
    record = dict(id=key, title='Replacement of Bridge No. 020027B in Bergen County',
                  _canonical_notice=True, source_id='county-bergen', source_name='Bergen County',
                  source_tier='county', source_status='open', status='open',
                  county='Bergen', county_provenance='SOURCE_RECORD_FIELD',
                  notice_type='construction', notice_subtype='construction',
                  contract_number='BC-C-26-022', due_date_raw='11/17/2099 5:00 PM ET',
                  official_url='https://agency.example/bid', source_url='https://agency.example/',
                  first_seen_at='2026-10-28T10:00:00Z')
    record.update(updates)
    return record


class ReviewStatusTests(unittest.TestCase):
    def resolve(self, raw):
        record = normalize_deadline(dict(raw), today=NOW.date())
        reconcile_authoritative_open_deadline(record, NOW)
        return apply_public_status(record, NOW)

    def test_burlington_parenthesized_timezone_parses_without_changing_source_text(self):
        raw = '11/5/2026 10:30:00 AM (ET)'
        record = normalize_deadline(notice(due_date_raw=raw))
        self.assertEqual(record['due_date_raw'], raw)
        self.assertEqual(record['deadline_at'], '2026-11-05T15:30:00Z')
        self.assertFalse(record['deadline_timezone_assumed'])

    def test_source_open_cannot_make_a_past_deadline_actionable(self):
        record = self.resolve(notice(due_date_raw='04/17/2026', source_status_authoritative=True))
        self.assertEqual(record['status'], 'needs_confirmation')
        self.assertTrue(record['deadline_conflict'])
        self.assertFalse(record['urgent'])
        self.assertEqual(record['source_status'], 'open')

    def test_submission_times_and_missing_times_are_distinct(self):
        for raw, expected in [('10/28/2026 10:30 AM ET', 'expired'),
                              ('10/28/2026 12:00 PM ET', 'expired'),
                              ('10/28/2026 3:00 PM ET', 'open'),
                              ('10/28/2026', 'needs_confirmation'),
                              ('10/29/2026', 'open'), ('TBD', 'needs_confirmation')]:
            with self.subTest(raw=raw):
                self.assertEqual(self.resolve(notice(due_date_raw=raw))['status'], expected)

    def test_closed_source_and_admin_approval_cannot_reopen_a_passed_deadline(self):
        self.assertEqual(self.resolve(notice(source_status='awarded'))['status'], 'expired')
        self.assertEqual(self.resolve(notice(status_override='approved', due_date_raw='01/01/2020'))['status'], 'expired')

    def test_planning_windows_are_separate_from_submission_deadlines(self):
        for raw, expected in [('Summer 2026', 'needs_confirmation'), ('Fall 2026', 'upcoming'),
                              ('Winter 2027', 'needs_confirmation'), ('September/October', 'needs_confirmation'),
                              ('11/17/2026', 'upcoming')]:
            record = notice(status='upcoming', source_status='upcoming', is_planned=True,
                            source_id='state-njdot-profserv-upcoming', due_date_raw=raw)
            with self.subTest(raw=raw):
                self.assertEqual(self.resolve(record)['status'], expected)
                self.assertEqual(notice_runner._enrich(dict(record), now=NOW)['status'], expected)

    def test_bridge_replacement_focus_respects_professional_service_type(self):
        record = notice(title='THE REPLACEMENT OF BERGEN COUNTY BRIDGE NO. 020027B KINDERKAMACK ROAD OVER PASCACK BROOK')
        self.assertEqual(work_focus(record)['key'], 'projects')
        self.assertEqual(work_focus(dict(record, notice_type='professional_services'))['key'], 'unclear')
        self.assertEqual(work_focus(notice(title='Purchase of office chairs'))['key'], 'unclear')


class ReviewPublicRoutesTests(unittest.TestCase):
    def setUp(self):
        self.client = main.app.test_client()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(main, 'apply_public_status', side_effect=lambda r: apply_public_status(r, NOW)))
        self.stack.enter_context(patch.object(main, 'deadline_is_past', side_effect=lambda r: deadline_is_past(r, NOW)))
        self.stack.enter_context(patch.object(main, '_homepage_today', return_value=NOW.date()))
        self.stack.enter_context(patch.object(main, 'load_public_sources', return_value=[]))
        self.records = [notice(), notice('old', due_date_raw='04/17/2026', source_status_authoritative=True),
                        notice('missing', due_date_raw='TBD'),
                        notice('current-forecast', source_id='state-njdot-profserv-upcoming', is_planned=True,
                               source_status='upcoming', status='upcoming', due_date_raw='Fall 2099'),
                        notice('elapsed-forecast', source_id='state-njdot-profserv-upcoming', is_planned=True,
                               source_status='upcoming', status='upcoming', due_date_raw='Summer 2026')]
        self.stack.enter_context(patch.object(main, 'load_public_opps', side_effect=lambda: self.records))
        self.stack.enter_context(patch.object(notice_routes, '_load_notices', side_effect=lambda: [main.enrich(r) for r in self.records]))
        self.stack.enter_context(patch.object(notice_routes, '_load_crawl_log', return_value=[]))

    def context(self, path, module):
        with patch.object(module, 'render_template', return_value='ok') as rendered:
            self.assertEqual(self.client.get(path).status_code, 200)
            return rendered.call_args.kwargs

    def test_counts_boards_notices_exports_and_calendar_share_actionable_status(self):
        home = self.context('/', main)
        self.assertEqual(home['stats']['open'], 1)
        self.assertEqual(home['stats']['pipeline'], 1)
        self.assertEqual(home['stats']['needs_confirmation'], 3)
        for path in ('/export/opportunities.csv', '/export/notices.csv'):
            rows = list(csv.DictReader(StringIO(self.client.get(path).get_data(as_text=True))))
            self.assertEqual({r['id'] for r in rows}, {'bid', 'current-forecast'})
        for path, module in (('/bids/construction', main), ('/notices', notice_routes)):
            self.assertEqual(self.context(path, module)['total'], 2)
            self.assertEqual(self.context(path+'?status=needs_confirmation', module)['total'], 3)
            self.assertEqual(self.context(path+'?status=forecast_review', module)['total'], 1)
        for key in ('old', 'missing', 'current-forecast', 'elapsed-forecast'):
            self.assertEqual(self.client.get(f'/opportunities/{key}/calendar.ics').status_code, 404)
        self.assertEqual(self.client.get('/opportunities/bid/calendar.ics').status_code, 200)

    def test_pagination_preserves_exact_filters_and_every_matching_record(self):
        self.records[:] = [notice(str(i), title=f'Bridge replacement in Bergen County on Route I-287 item {i:02d}',
                                   contract_number=f'BC-{i:02d}') for i in range(61)]
        self.records.append(notice('other', source_id='other-agency'))
        filters = dict(status='open', q='bridge', county='Bergen', work='projects', sort='newest')
        for endpoint, module in (('/bids/construction', main), ('/notices', notice_routes)):
            url = endpoint+'?'+urlencode(dict(filters, **({'source': 'county-bergen', 'corridor': 'I-287'} if endpoint == '/notices' else {})))
            seen, sizes = set(), []
            for page in range(1, 4):
                context = self.context(url, module)
                # The typed board intentionally also shows the other source.
                expected_total = 61 if endpoint == '/notices' else 62
                self.assertEqual(context['total'], expected_total)
                rows = [r for group in context['feed_groups'] for r in group['opportunities']]
                page_ids = {r['id'] for r in rows}
                self.assertFalse(page_ids & seen)
                seen |= page_ids
                sizes.append(len(rows))
                pagination = context['pagination']
                self.assertEqual(pagination['page'], page)
                for link in (pagination['next'], pagination['previous']):
                    if link:
                        params = parse_qs(urlsplit(link).query)
                        for key, value in filters.items():
                            self.assertEqual(params[key], [value])
                        if endpoint == '/notices':
                            self.assertEqual(params['source'], ['county-bergen'])
                            self.assertEqual(params['corridor'], ['I-287'])
                url = pagination['next']
            self.assertEqual(sizes, [25, 25, expected_total-50])
            self.assertEqual(len(seen), expected_total)

    def test_public_help_explains_free_access_without_disclosing_identity(self):
        for path in ('/about', '/contact', '/faq'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            soup = BeautifulSoup(response.data, 'html.parser')
            self.assertIsNone(soup.select_one('.topnav a[href="/admin/login"]'))
            self.assertIsNone(soup.select_one('a[href^="mailto:"]'))
            self.assertIsNotNone(soup.select_one('a[href="/sources"]'))
            self.assertNotIn('Updated daily', soup.get_text())
        with self.client.session_transaction() as session:
            session['admin'] = True
        soup = BeautifulSoup(self.client.get('/about').data, 'html.parser')
        self.assertIsNotNone(soup.select_one('.topnav a[href="/admin"]'))


if __name__ == '__main__':
    unittest.main()
