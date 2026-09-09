import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from app.core.project_facts import parse_njdot_facts, project_facts_display
from crawlers.project_facts import collect_njdot_facts

TEXT = '''Contract No. 038153910
Estimated Completion Date: 12/22/2028
Estimated Range (for Information Purpose Only): Range between $10,000,001 to $20,000,000
Contractors Prequalified in one of these
Work Types are eligible to bid this project: 4 or 5
Right of Way Required: Yes'''


class ProjectFactsTests(unittest.TestCase):
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
