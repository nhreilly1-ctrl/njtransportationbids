import copy
import unittest
from unittest.mock import patch
from app.core.work_focus import work_focus, matches_work_focus
import app.main as main
import app.notice_routes as routes


class WorkFocusTests(unittest.TestCase):
    def test_title_evidence(self):
        for title, key in [('Rock salt', 'supplies'), ('Snow plow parts', 'supplies'), ('Heavy duty towing', 'support'), ('Tree trimming', 'support'), ('Milling & resurfacing', 'projects'), ('Construction project management', 'professional')]:
            with self.subTest(title=title):
                self.assertEqual(work_focus({'title': title})['key'], key)

    def test_ambiguous_and_agency_names_do_not_classify(self):
        for record in [{'title': 'Annual contract', 'source_name': 'Tree Trimming Agency'}, {'title': 'Bridge replacement engineering services'}, {'title': 'Rock salt and snow removal'}, {'title': 'Purchase of land'}, {'title': 'Annual contract', 'notice_type': 'construction'}]:
            self.assertEqual(work_focus(record)['key'], 'unclear')

    def test_no_mutation_or_default_exclusion(self):
        record = {'title': 'Rock salt', 'notice_type': 'construction', 'counties': []}
        original = copy.deepcopy(record)
        work_focus(record)
        self.assertEqual(record, original)
        self.assertTrue(matches_work_focus(record, ''))
        self.assertTrue(matches_work_focus(record, 'invalid'))
        self.assertFalse(matches_work_focus(record, 'projects'))

    def test_supervision_and_professional_forecasts_are_not_projects(self):
        self.assertEqual(work_focus({'title': 'Order for Professional Services: Supervision of Construction, Bridge Repairs and Resurfacing'})['key'], 'unclear')
        self.assertEqual(work_focus({'title': 'Pavement Preservation North', 'notice_type': 'professional_services'})['key'], 'unclear')

    def test_public_routes_filter_without_hiding_default(self):
        records = [dict(id=str(i), title=title, notice_type='construction', status='open', source_name='Test Agency', source_id='test', due_date_raw='12/31/2068', _canonical_notice=True) for i, title in enumerate(['Rock salt', 'Milling & resurfacing', 'Annual contract'])]
        with patch.object(main, 'load_public_opps', return_value=records):
            client = main.app.test_client()
            all_work = client.get('/bids/construction').data
            for record in records:
                self.assertIn(record['title'].replace('&', '&amp;').encode(), all_work)
            filtered = client.get('/bids/construction?work=supplies&sort=closing').data
            self.assertIn(b'Rock salt', filtered)
            self.assertNotIn(b'Milling &amp; resurfacing', filtered)
            self.assertIn(b'Remove Work focus filter', filtered)
        enriched = [main.enrich(r) for r in records]
        self.assertEqual(len(routes._filter_notices(enriched, work='supplies', source_id='test')), 1)
        self.assertEqual(routes._filter_notices(enriched, work='supplies', q='paving'), [])
        with patch.object(routes, '_load_notices', return_value=enriched):
            response = main.app.test_client().get('/notices?work=support')
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(b'Rock salt', response.data)
