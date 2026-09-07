import unittest
from unittest.mock import patch

from app.core.freshness import stamp_refresh
from app.core.milestones import schedule_indicator
from crawlers.document_watch import fingerprint, inspect_documents

URL = 'https://www.drjtbc.org/wp-content/uploads/test.pdf'


def record(digest='abc', state='ok'):
    return {'status': 'open', 'due_date_raw': 'September 10, 2026',
            'document_checks': [{'url': URL, 'title': 'RFP', 'state': state,
                                 **({'sha256': digest} if state == 'ok' else {})}]}


class DocumentChangesTests(unittest.TestCase):
    def test_baseline_unchanged_and_changed(self):
        first = record()
        stamp_refresh(first, None, '2026-09-07T12:00:00Z')
        self.assertFalse(first['document_change_detected'])
        same = record()
        stamp_refresh(same, first, '2026-09-08T12:00:00Z')
        self.assertIsNone(same['materially_changed_at'])
        changed = record('def')
        stamp_refresh(changed, same, '2026-09-09T12:00:00Z')
        self.assertTrue(changed['document_change_detected'])
        self.assertIn('Document changed; review required', changed['change_labels'])
        self.assertEqual(changed['due_date_raw'], first['due_date_raw'])
        self.assertEqual(changed['document_checks'][0]['previous_sha256'], 'abc')
        self.assertEqual(schedule_indicator(changed), 'Document changed; review required')
        again = record('def')
        stamp_refresh(again, changed, '2026-09-10T12:00:00Z')
        self.assertEqual(again['materially_changed_at'], changed['materially_changed_at'])
        self.assertTrue(again['document_change_detected'])

    def test_outage_retains_baseline_and_recovery_compares(self):
        first = record()
        stamp_refresh(first, None, '2026-09-07T12:00:00Z')
        failed = record(state='unavailable')
        stamp_refresh(failed, first, '2026-09-08T12:00:00Z')
        self.assertEqual(failed['document_checks'][0]['sha256'], 'abc')
        self.assertTrue(failed['document_check_unavailable'])
        self.assertIsNone(failed['materially_changed_at'])
        recovered = record('def')
        stamp_refresh(recovered, failed, '2026-09-09T12:00:00Z')
        self.assertTrue(recovered['document_change_detected'])
        self.assertFalse(recovered['document_check_unavailable'])

    def test_new_url_is_baseline_not_replacement(self):
        first = record()
        new = record('def')
        new['document_checks'][0]['url'] = URL + '?version=2'
        stamp_refresh(new, first, '2026-09-08T12:00:00Z')
        self.assertFalse(new['document_change_detected'])

    def test_download_limits_and_non_pdf(self):
        with patch('crawlers.document_watch.requests.get') as get:
            response = get.return_value.__enter__.return_value
            response.status_code = 200
            response.iter_content.return_value = [b'%PDF-1.7\nexample']
            result = fingerprint(URL)
            self.assertEqual(result['state'], 'ok')
            self.assertEqual(len(result['sha256']), 64)
            self.assertFalse(get.call_args.kwargs['allow_redirects'])
            response.iter_content.return_value = [b'<html>Access denied</html>']
            self.assertEqual(fingerprint(URL)['state'], 'unavailable')
            response.iter_content.return_value = [b'%PDF-long']
            with patch('crawlers.document_watch.MAX_BYTES', 5):
                self.assertEqual(fingerprint(URL)['state'], 'unavailable')
            response.status_code = 302
            self.assertEqual(fingerprint(URL)['state'], 'unavailable')

    def test_unsupported_urls_never_requested(self):
        with patch('crawlers.document_watch.requests.get') as get:
            for url in ('http://127.0.0.1/test.pdf', 'https://example.com/test.pdf',
                        'https://www.drjtbc.org:bad/test.pdf', 'https://www.drjtbc.org/login'):
                self.assertEqual(fingerprint(url)['state'], 'unavailable')
            get.assert_not_called()

    def test_unique_fetches_and_bounded_source(self):
        rows = [{'official_url': URL, 'published_addenda': [{'title': 'Again', 'url': URL}]}]
        with patch('crawlers.document_watch.fingerprint', return_value={'state': 'ok', 'sha256': 'abc'}) as fetch:
            inspect_documents(rows)
            fetch.assert_called_once_with(URL)
            self.assertEqual(len(rows[0]['document_checks']), 1)
            rows = [{'official_url': URL + '?v=' + str(i)} for i in range(26)]
            fetch.reset_mock()
            inspect_documents(rows)
            self.assertEqual(fetch.call_count, 24)
            self.assertEqual(rows[-1]['document_checks'][0]['state'], 'unavailable')

    def test_merge_preserves_failed_check_baseline(self):
        from crawlers.notice_runner import _merge
        old = dict(record(), id='a', source_id='state-drjtbc-profserv')
        fresh = dict(record(state='unavailable'), id='a', source_id='state-drjtbc-profserv')
        merged = _merge([old], [fresh])[0]
        self.assertEqual(merged['document_checks'][0]['sha256'], 'abc')
        self.assertFalse(merged['document_change_detected'])

    def test_document_warning_render(self):
        from app import main
        from test_milestones import MilestoneTests, entry
        raw = MilestoneTests().parse(entry('753'))[0]
        raw.update(record())
        previous = dict(raw, document_checks=[dict(raw['document_checks'][0], sha256='old')])
        stamp_refresh(raw, previous, '2026-09-07T12:00:00Z')
        with main.app.test_request_context('/'):
            html = main.render_template('opportunity_detail.html', opp=main.enrich(raw),
                seo_title='Test', seo_description='', canonical_url='https://example.com',
                site_url='https://example.com', related=[], readiness=[])
        self.assertIn('Document changed; review required.', html)
        self.assertIn('metadata-only changes', html)
        self.assertIn('change detected 2026-09-07', html)


if __name__ == '__main__':
    unittest.main()
