import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from app.core.project_facts import parse_njdot_facts, project_facts_display, parse_njdot_bid_date
from app.core.deadlines import normalize_deadline
from app.core.document_deadlines import document_deadline_warning
from copy import deepcopy
from crawlers.project_facts import collect_njdot_facts

TEXT = '''Contract No. 038153910
Estimated Completion Date: 12/22/2028
Estimated Range (for Information Purpose Only): Range between $10,000,001 to $20,000,000
Contractors Prequalified in one of these
Work Types are eligible to bid this project: 4 or 5
Right of Way Required: Yes'''


class ProjectFactsTests(unittest.TestCase):
    def discrepancy_record(self):
        return {'id': 'pdf-date-test', '_canonical_notice': True,
                'source_id': 'state-njdot-construction', 'notice_type': 'construction',
                'title': 'Route 1 bridge', 'status': 'open', 'source_name': 'NJDOT',
                'contract_number': '027153030', 'official_url': 'https://dot.nj.gov/test.pdf',
                'due_date_raw': '09/24/2099',
                'project_facts': {'state': 'ok', 'contract': '027153030',
                    'url': 'https://dot.nj.gov/test.pdf', 'sha256': 'abc',
                    'checked_at': datetime.now(timezone.utc).isoformat(),
                    'bid_date': parse_njdot_bid_date('Contract # 027153030 Project Bid Date: 8/25/2099', '027153030'),
                    'items': [{'kind': 'estimate', 'value': '$100', 'evidence': 'test', 'page': 1}]}}

    def test_pdf_bid_date_uses_exact_contract_and_explicit_label(self):
        text = 'Contract # 027153030 Project Advertisement Date: 7/28/26 Project Bid Date: 8/25/26'
        self.assertEqual(parse_njdot_bid_date(text, '027153030')['date'], '2026-08-25')
        self.assertIsNone(parse_njdot_bid_date(text, '027153031'))
        self.assertIsNone(parse_njdot_bid_date(text.replace('8/25/26', '2/31/26'), '027153030'))
        self.assertIsNone(parse_njdot_bid_date(text + ' Project Bid Date: 9/24/26', '027153030'))
        self.assertIsNone(parse_njdot_bid_date(text + ' Contract No. 999', '027153030'))
        self.assertIsNone(parse_njdot_bid_date('Contract # 027153030 Office opens 10 AM on 8/25/26', '027153030'))

    def test_contract_hash_supported_without_dropping_qualification_footnote(self):
        text = TEXT.replace('Contract No.', 'Contract #').replace('4 or 5', '4 or 5*')
        self.assertEqual([f['kind'] for f in parse_njdot_facts(text, '038153910')], ['estimate', 'completion'])

    def test_conflict_preserves_listing_and_does_not_invent_pdf_time(self):
        item = self.discrepancy_record()
        normalize_deadline(item)
        self.assertEqual(item['due_date_raw'], '09/24/2099')
        self.assertEqual(item['due_date_parsed'], '2099-09-24')
        self.assertTrue(item['deadline_conflict'])
        self.assertIsNone(item['deadline_at'])
        self.assertIsNone(item['days_until_due'])
        self.assertIn('linked PDF date differs', item['deadline_display'])
        self.assertTrue(project_facts_display(item)['needs_review'])
        self.assertEqual(project_facts_display(item)['items'], [])

    def test_agreement_wrong_identity_failure_and_stale_pack_do_not_claim_conflict(self):
        item = self.discrepancy_record()
        self.assertIsNone(document_deadline_warning(item, '2099-08-25'))
        for key, value in [('contract', 'wrong'), ('url', 'https://dot.nj.gov/other.pdf'),
                           ('checked_at', '2000-01-01T00:00:00Z'), ('state', 'unavailable'), ('sha256', '')]:
            changed = deepcopy(item)
            changed['project_facts'][key] = value
            self.assertIsNone(document_deadline_warning(changed, '2099-09-24'))

    def test_disagreement_warns_detail_blocks_calendar_and_excludes_urgency(self):
        import app.main as main
        from app.core.scanning import closing_soon
        item = self.discrepancy_record()
        with patch.object(main, 'load_public_opps', return_value=[item]):
            client = main.app.test_client()
            response = client.get('/opportunities/pdf-date-test')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Listing and linked PDF dates differ', response.data)
            self.assertNotIn(b'Add deadline to calendar', response.data)
            self.assertNotIn(b'$100', response.data)
            self.assertEqual(client.get('/opportunities/pdf-date-test/calendar.ics').status_code, 404)
        enriched = main.enrich(item)
        self.assertEqual(enriched['status'], 'open')
        self.assertFalse(closing_soon(enriched))
        self.assertIn(enriched, main.group_opportunity_scan([enriched])[3])

    def test_detail_renders_fact_and_source(self):
        import app.main as main
        template = main.app.jinja_env.get_template('opportunity_detail.html')
        self.assertIsNotNone(template)
        record = {'id': 'facts-test', '_canonical_notice': True, 'title': 'Route 94 project', 'notice_type': 'construction', 'status': 'open', 'source_id': 'state-njdot-construction', 'source_name': 'NJDOT', 'contract_number': '038153910', 'official_url': 'https://dot.nj.gov/test.pdf'}
        record['project_facts'] = {'state': 'ok', 'url': record['official_url'], 'contract': record['contract_number'], 'sha256': 'abc', 'checked_at': datetime.now(timezone.utc).isoformat(), 'items': parse_njdot_facts(TEXT, record['contract_number'])}
        with patch.object(main, 'load_public_opps', return_value=[record]):
            response = main.app.test_client().get('/opportunities/facts-test')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'$10,000,001', response.data)
        self.assertIn(b'https://dot.nj.gov/test.pdf#page=1', response.data)

    def test_published_fields(self):
        facts = parse_njdot_facts(TEXT, '038153910')
        self.assertEqual(len(facts), 3)
        self.assertEqual(facts[-1]['value'], '4 or 5')
        self.assertEqual(facts[0]['value'], 'Range between $10,000,001 to $20,000,000')

    def test_no_guessing_or_wrong_contract(self):
        self.assertEqual(parse_njdot_facts(TEXT, '038153911'), [])
        self.assertEqual(parse_njdot_facts('Contract No. 038153910 General $500 fee', '038153910'), [])
        self.assertEqual(parse_njdot_facts(TEXT + TEXT, '038153910'), [])

    def test_failure_returns_no_stale_items(self):
        record = {'official_url': 'https://dot.nj.gov/test.pdf', 'contract_number': '038153910'}
        self.assertEqual(collect_njdot_facts(record, lambda _: None, '2026-09-09')['items'], [])
        self.assertEqual(collect_njdot_facts(record, lambda _: type('R', (), {'content': b'<html>error'})(), '2026-09-09')['state'], 'unavailable')

    def test_freshness_and_identity_gate(self):
        record = {'source_id': 'state-njdot-construction', 'official_url': 'https://dot.nj.gov/test.pdf', 'contract_number': '038153910'}
        record['project_facts'] = {'state': 'ok', 'url': record['official_url'], 'contract': record['contract_number'], 'sha256': 'abc', 'checked_at': '2026-09-09T12:00:00+00:00', 'items': parse_njdot_facts(TEXT, record['contract_number'])}
        now = datetime(2026, 9, 9, 13, tzinfo=timezone.utc)
        self.assertEqual(len(project_facts_display(record, now)['items']), 3)
        self.assertTrue(project_facts_display(record, datetime(2026, 9, 12, tzinfo=timezone.utc))['needs_review'])
        record['official_url'] += 'changed'
        self.assertTrue(project_facts_display(record, now)['needs_review'])
