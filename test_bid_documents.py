"""Advertised visibility, evidence precedence, and safe source retirement."""
import csv
from copy import deepcopy
from datetime import datetime
from io import StringIO
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from app import main, notice_routes
from app.core.bid_documents import choose_bid_document, parse_bid_deadline, publication_date, retain_bid_document_review
from app.core.deadlines import EASTERN, apply_public_status, matches_public_status, normalize_deadline, reconcile_authoritative_open_deadline
from app.core.freshness import stamp_refresh
from crawlers import notice_crawlers, notice_runner
from crawlers.bid_documents import collect_bid_document_review
from test_review_followup import notice

NOW = datetime(2026, 10, 28, 12, tzinfo=EASTERN)
PDF = 'https://agency.example/bid.pdf'


def document(raw='2099-11-05', **updates):
    item = dict(url=PDF, title='Advertisement', kind='advertisement', state='ok',
                sha256='abc', identity_verified=True, checked_at='2026-10-28T12:00:00Z',
                deadline=dict(raw=raw, date=raw[:10], evidence='Bids due ' + raw, page=1))
    item.update(updates)
    return item


def reviewed(*documents, **updates):
    record = notice(official_url=PDF, due_date_raw='11/17/2099')
    record['bid_document_review'] = dict(state='resolved', listing_url=PDF,
        contract=record['contract_number'], checked_at='2026-10-28T12:00:00Z', documents=list(documents))
    record.update(updates)
    return record


def resolve(record):
    item = normalize_deadline(deepcopy(record), today=NOW.date())
    reconcile_authoritative_open_deadline(item, NOW)
    return apply_public_status(item, NOW)


class BidDocumentTests(unittest.TestCase):
    def test_published_document_date_orders_versions_not_the_deadline_or_fetch_order(self):
        older = document('2099-12-01', published_date='2026-10-01')
        newer = document('2099-11-05', url=PDF+'?new', published_date='2026-10-28')
        self.assertEqual(choose_bid_document([newer, older])[0], newer)
        self.assertEqual(choose_bid_document([newer, dict(older, kind='addendum', sequence=1)])[0], newer)
        self.assertEqual(publication_date(['Project Advertisement Date: 10/28/2026']), '2026-10-28')
        self.assertIsNone(publication_date(['Pre-bid conference: October 28, 2026']))

    def test_same_day_time_conflict_also_uses_the_document(self):
        item = resolve(reviewed(document('2099-11-05T19:00:00Z'), due_date_raw='11/05/2099 3:00 PM ET'))
        self.assertEqual(item['deadline_at'], '2099-11-05T19:00:00Z')
        self.assertTrue(item['document_deadline_warning']['resolved'])
        self.assertFalse(item['deadline_conflict'])

    def test_document_controls_listing_and_expiry_without_erasing_source_text(self):
        item = resolve(reviewed(document('2026-10-27'), source_status_authoritative=True))
        self.assertEqual(item['due_date_raw'], '11/17/2099')
        self.assertEqual(item['due_date_parsed'], '2026-10-27')
        self.assertEqual(item['deadline_basis'], 'bid_document')
        self.assertEqual(item['status'], 'expired')
        self.assertFalse(item['deadline_conflict'])
        self.assertTrue(item['document_deadline_warning']['resolved'])

    def test_latest_addendum_controls_even_when_it_moves_closing_earlier(self):
        older = document('2099-12-01', kind='addendum', sequence=1)
        newer = document('2099-11-05', kind='addendum', sequence=2, url=PDF+'?v=2')
        self.assertEqual(resolve(reviewed(older, newer))['due_date_parsed'], '2099-11-05')
        self.assertEqual(choose_bid_document([newer, older])[0], newer)
        for metadata in ({}, {'sequence': 2}):
            other = document(url=PDF+'?other', kind='addendum', **metadata)
            selected, reason = choose_bid_document([newer, other])
            self.assertIsNone(selected)
            self.assertTrue(reason)

    def test_unreadable_new_version_stays_visible_without_using_the_old_date(self):
        old = document(kind='addendum', sequence=1)
        new = document(url=PDF+'?v=2', kind='addendum', sequence=2, state='unavailable', deadline=None)
        raw = reviewed(old, new)
        raw['bid_document_review']['state'] = 'needs_review'
        item = resolve(raw)
        self.assertEqual(item['deadline_basis'], 'agency_listing')
        self.assertEqual(item['status'], 'needs_confirmation')
        self.assertTrue(matches_public_status(item, 'active'))
        self.assertTrue(matches_public_status(item, 'deadline_review'))

    def test_failed_check_retains_verified_date_but_changed_link_requires_review(self):
        previous = reviewed(document())
        fresh = reviewed()
        fresh['bid_document_review'].update(state='unavailable')
        retain_bid_document_review(fresh, previous)
        self.assertEqual(resolve(fresh)['due_date_parsed'], '2099-11-05')
        self.assertIn('last verified', fresh['bid_document_review']['recheck_note'])
        changed = reviewed(document(url=PDF+'?new', state='unavailable'))
        changed['bid_document_review']['state'] = 'unavailable'
        retain_bid_document_review(changed, previous)
        self.assertEqual(changed['bid_document_review']['documents'][0]['url'], PDF+'?new')

    def test_document_identity_mismatch_cannot_override(self):
        for field, value in [('contract', 'wrong'), ('listing_url', 'https://agency.example/reissued.pdf')]:
            raw = reviewed(document())
            raw['bid_document_review'][field] = value
            self.assertEqual(resolve(raw)['due_date_parsed'], '2099-11-17')

    def test_first_failed_packet_refresh_keeps_legacy_verified_njdot_date(self):
        from test_project_facts import ProjectFactsTests
        old = ProjectFactsTests().discrepancy_record()
        fresh = deepcopy(old)
        fresh['bid_document_review'] = dict(state='unavailable', contract=old['contract_number'],
            listing_url=old['official_url'], checked_at='2026-10-28T12:00:00Z',
            documents=[dict(url=old['official_url'], state='unavailable')])
        retain_bid_document_review(fresh, old)
        self.assertEqual(resolve(fresh)['due_date_parsed'], '2099-08-25')
        self.assertIn('last verified', fresh['bid_document_review']['recheck_note'])

    def test_closing_date_change_is_material_but_routine_recheck_is_not(self):
        old = reviewed(document())
        stamp_refresh(old, None, '2026-10-27T12:00:00Z')
        same = deepcopy(old)
        same['bid_document_review']['documents'][0]['checked_at'] = '2026-10-28T12:00:00Z'
        stamp_refresh(same, old, '2026-10-28T12:00:00Z')
        self.assertIsNone(same['materially_changed_at'])
        new = reviewed(document('2099-11-06', sha256='changed'))
        stamp_refresh(new, old, '2026-10-28T12:00:00Z')
        self.assertIn('Closing date changed', new['change_labels'])
        self.assertIn('Bid document changed', new['change_labels'])

    def test_njtransit_submission_time_and_plausible_false_positives(self):
        text = ('INVITATION FOR BID (IFB) NO. 26-021X. Notice is hereby given that this is an '
                'electronic bid submission received via the Internet until 2:00 PM EST on '
                'Tuesday, December 15, 2026, by NJ TRANSIT. Pre-Bid Conference November 3, 2026 at 10:00 AM EST.')
        parsed = parse_bid_deadline([text], '26-021X')
        self.assertEqual(parsed['date'], '2026-12-15')
        self.assertIn('2:00 PM EST', parsed['raw'])
        self.assertEqual(parse_bid_deadline([text], 'IFB No. 26-021X')['date'], '2026-12-15')
        self.assertIsNone(parse_bid_deadline([text], '26-022X'))
        self.assertIsNone(parse_bid_deadline(['IFB 26-021X. Pre-bid conference responses are due on December 15, 2026.'], '26-021X'))
        self.assertIsNone(parse_bid_deadline(['IFB 26-021X. Questions must be submitted by December 15, 2026.'], '26-021X'))

    def test_collector_hash_identity_and_document_evidence(self):
        raw = reviewed()
        text = 'Contract BC-C-26-022. Closing Date: November 5, 2099'
        reader = SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: text)])
        with patch('crawlers.bid_documents.PdfReader', return_value=reader):
            pack = collect_bid_document_review(raw, lambda _: SimpleNamespace(content=b'%PDF-test'), '2026-10-28T12:00:00Z')
        self.assertEqual(pack['state'], 'resolved')
        self.assertEqual(pack['documents'][0]['deadline']['date'], '2099-11-05')
        self.assertEqual(len(pack['documents'][0]['sha256']), 64)
        raw.update(official_url='https://agency.example/detail', deadline_evidence_url=PDF)
        with patch('crawlers.bid_documents.PdfReader', return_value=reader):
            pack = collect_bid_document_review(raw, lambda _: SimpleNamespace(content=b'%PDF-test'), '2026-10-28T12:00:00Z')
        self.assertEqual(pack['state'], 'resolved')
        self.assertEqual(pack['documents'][0]['url'], PDF)


class AdvertisedLifecycleTests(unittest.TestCase):
    def test_past_calendar_rows_can_reopen_only_when_the_document_has_a_future_deadline(self):
        item = resolve(reviewed(document(), source_status='past_calendar_event', due_date_raw='10/01/2026'))
        self.assertEqual(item['status'], 'open')
        past = resolve(notice(source_status='past_calendar_event', due_date_raw='10/01/2026'))
        self.assertEqual(past['status'], 'expired')

    def test_generic_posted_date_is_not_a_submission_deadline(self):
        html = '<main><h1>Bids</h1><p>Posted October 1, 2026: <a href="bid.pdf">Bid #26-1 Bridge replacement</a></p></main>'
        source = dict(id='test', name='Test', url='https://agency.example/', source_tier='county', entity_type='County')
        with patch.object(notice_crawlers, '_get', return_value=SimpleNamespace(text=html)):
            rows = notice_crawlers.parse_generic_html_list(source)
        self.assertEqual(rows[0]['due_date_raw'], '')
        self.assertTrue(rows.listing_complete)
        self.assertEqual(notice_crawlers._classify_transport_scope('Howell Garage Aboveground Storage Tank Upgrade'), 'construction')
        self.assertIsNone(notice_crawlers._classify_transport_scope('Purchase and delivery of general storage tanks'))

    def test_no_date_and_elapsed_forecasts_remain_posted_until_source_removal(self):
        for raw in ('', 'TBD', 'date unavailable'):
            item = resolve(notice(due_date_raw=raw))
            self.assertEqual(item['status'], 'open')
            self.assertEqual(item['deadline_display'], 'No known closing date')
            self.assertTrue(matches_public_status(item, 'active'))
            self.assertIsNone(item['deadline_at'])
        forecast = resolve(notice(source_id='state-njdot-profserv-upcoming', is_planned=True,
                                  status='upcoming', source_status='upcoming', due_date_raw='Summer 2026'))
        self.assertEqual(forecast['status'], 'upcoming')
        self.assertTrue(forecast['forecast_needs_update'])
        self.assertEqual(resolve(dict(forecast, source_inactive=True))['status'], 'expired')

    def test_unknown_deadline_removed_only_after_complete_successful_listing(self):
        old = notice(due_date_raw='')
        self.assertEqual(resolve(notice_runner._merge([old], [], set())[0])['status'], 'open')
        gone = notice_runner._merge([old], [], {old['source_id']})[0]
        self.assertTrue(gone['source_inactive'])
        self.assertEqual(resolve(gone)['status'], 'expired')
        self.assertFalse(matches_public_status(resolve(gone), 'active'))
        returned = notice_runner._merge([gone], [notice(due_date_raw='')], {old['source_id']})[0]
        self.assertFalse(returned['source_inactive'])
        self.assertTrue(returned['last_seen_advertised_at'])

    def test_complete_generic_snapshot_retires_absent_records_but_partial_and_errors_do_not(self):
        source = dict(id='test', name='Test', parser='generic_html_list', allow_empty=True)
        complete = notice_crawlers._complete_listing(BeautifulSoup('<main><h1>Bids</h1><p>No open bids are posted</p></main>', 'html.parser'), [])
        self.assertTrue(complete.listing_complete)
        with patch.object(notice_runner, 'crawl_source', return_value=complete), patch.object(notice_runner, '_log_crawl'):
            self.assertEqual(notice_runner.run_crawl([source])[1], {'test'})
        partial = notice_crawlers._complete_listing(BeautifulSoup('<main><h1>Bids</h1><a rel="next">Next</a></main>', 'html.parser'), [notice()])
        self.assertFalse(partial.listing_complete)
        with patch.object(notice_runner, 'crawl_source', side_effect=RuntimeError('source unavailable')), patch.object(notice_runner, '_log_crawl'):
            self.assertEqual(notice_runner.run_crawl([source])[1], set())

    def test_public_boards_csv_detail_and_calendar_follow_the_same_rules(self):
        raw = notice(due_date_raw='')
        with (patch.object(main, 'load_public_opps', return_value=[raw]),
              patch.object(notice_routes, '_load_notices', side_effect=lambda: [main.enrich(raw)])):
            client = main.app.test_client()
            for path in ('/bids/construction', '/notices', '/opportunities/bid'):
                page = client.get(path)
                self.assertEqual(page.status_code, 200)
                self.assertIn(b'No known closing date', page.data)
            for path in ('/export/opportunities.csv', '/export/notices.csv'):
                rows = list(csv.DictReader(StringIO(client.get(path).get_data(as_text=True))))
                self.assertEqual([r['id'] for r in rows], ['bid'])
            self.assertEqual(client.get('/opportunities/bid/calendar.ics').status_code, 404)
        item = reviewed(document('2099-11-05'))
        with patch.object(main, 'load_public_opps', return_value=[item]):
            calendar = main.app.test_client().get('/opportunities/bid/calendar.ics')
            self.assertEqual(calendar.status_code, 200)
            self.assertIn(b'DTSTART;VALUE=DATE:20991105', calendar.data)
            self.assertIn(b'Source deadline: 2099-11-05', calendar.data)
            self.assertNotIn(b'Source deadline: 11/17/2099', calendar.data)


if __name__ == '__main__':
    unittest.main()
