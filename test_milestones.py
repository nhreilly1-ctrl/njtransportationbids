import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from app.core.milestones import milestone_display, schedule_indicator
from app.core.freshness import stamp_refresh
from crawlers.notice_crawlers import parse_drjtbc
from crawlers.notice_sources import SOURCES_BY_ID


def entry(identity, question='August 25, 2026', meeting='August 18, 2026 10:00am'):
    return f'''<div class="entry row" id="{identity}">
    <strong>Contract No. C-{identity}A</strong>
    <div class="meta_title">Bridge inspection {identity}</div>
    <p class="meta_description">Professional engineering services for Construction Management / Inspection Services for bridge {identity}</p>
    <div class="contract-files-list"><a href="/rfp.pdf">RFP</a></div>
    <span class="meta_date"><strong>Solicitation Posted: </strong>August 6, 2026</span>
    <span class="meta_date"><strong>Pre-Proposal Meeting: </strong>{meeting}</span>
    <span class="meta_date"><strong>Deadline for Inquiries: </strong>{question}</span>
    <span class="meta_date"><strong>Response to Inquiries: </strong>September 1, 2026</span>
    <span class="meta_date"><strong>Solicitation Deadline: </strong><span>September 17, 2026 2:00pm</span></span>
    </div>'''


class MilestoneTests(unittest.TestCase):
    def test_schedule_indicator_prioritizes_next_and_preserves_uncertainty(self):
        record = dict(status='open', milestones_display=[
            dict(label='Question deadline', date='2099-09-03', display='Sep 3 (time not published)', past=False),
            dict(label='Pre-proposal meeting', date='2099-09-01', display='Sep 1 at 2 PM ET (time zone assumed)', past=False)],
            published_addenda=[{'url': 'https://example.com/addendum'}])
        self.assertTrue(schedule_indicator(record).startswith('Pre-proposal meeting:'))
        self.assertIn('time zone assumed', schedule_indicator(record))
        self.assertIn('Review agency addenda', schedule_indicator(record))
        for m in record['milestones_display']:
            m['past'] = True
        self.assertIn('dates have passed', schedule_indicator(record))
        record['milestones_display'][0]['date'] = None
        self.assertIn('needs confirmation', schedule_indicator(record))
        record['status'] = 'expired'
        self.assertEqual(schedule_indicator(record), '')
        self.assertEqual(schedule_indicator(dict(status='open')), '')

    def test_canonical_feed_and_shortlist_receive_indicator(self):
        from app import main, notice_routes
        raw = self.parse(entry('753'))[0]
        raw.update(_canonical_notice=True, due_date_raw='September 17, 2099 2:00pm')
        record = main.enrich(raw)
        self.assertTrue(record['schedule_indicator'])
        with patch.object(notice_routes, '_load_notices', return_value=[record]):
            html = main.app.test_client().get('/notices').get_data(as_text=True)
        self.assertIn('#agency-schedule', html)
        with patch.object(main, 'load_public_opps', return_value=[raw]):
            html = main.app.test_client().get('/shortlist').get_data(as_text=True)
        self.assertIn('schedule_indicator', html)
        self.assertIn('Published meeting/question dates have passed', html)

    def parse(self, html):
        with patch('crawlers.notice_crawlers._get', return_value=SimpleNamespace(text=html)):
            return parse_drjtbc(SOURCES_BY_ID['state-drjtbc-profserv'])

    def test_project_isolation_and_unique_ids(self):
        first, second = self.parse(entry('753') + entry('816', 'June 4, 2026'))
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(first['due_date_raw'], 'September 17, 2026 2:00pm')
        self.assertEqual(first['procurement_milestones'][1]['raw'], 'August 25, 2026')
        self.assertEqual(second['procurement_milestones'][1]['raw'], 'June 4, 2026')
        self.assertTrue(second['procurement_milestones'][1]['source_url'].endswith('#816'))
        self.assertEqual(first['contract_number'], 'C-753A')

    def test_date_only_and_unknown_do_not_invent_times(self):
        record = self.parse(entry('753', 'TBD', ''))[0]
        self.assertEqual(len(record['procurement_milestones']), 1)
        self.assertIn('TBD', milestone_display(record)[0]['display'])
        record = self.parse(entry('753'))[0]
        display = milestone_display(record)
        self.assertIn('time not published', display[1]['display'])
        self.assertNotRegex(display[1]['display'], r'\b\d{1,2}:\d{2}\b|\b(?:AM|PM)\b')
        self.assertIn('10:00 AM', display[0]['display'])
        self.assertIn('time zone assumed', display[0]['display'])

    def test_missing_layout_fails_not_silently_empty(self):
        with self.assertRaises(RuntimeError):
            self.parse('<p>Website unavailable</p>')

    def test_addenda_are_project_scoped_and_change_tracked(self):
        original = entry('753')
        revised = original.replace('</a></div>', '</a><a href="/addendum.pdf">ADDENDUM NO. 1</a></div>')
        first, second = self.parse(revised + entry('816'))
        self.assertEqual(first['published_addenda'], [{'title': 'ADDENDUM NO. 1',
            'url': 'https://www.drjtbc.org/addendum.pdf'}])
        self.assertEqual(second['published_addenda'], [])
        stamp_refresh(first, self.parse(original)[0], '2026-09-07T12:00:00Z')
        self.assertIn('Published addenda list changed', first['change_labels'])
        self.assertEqual(first['due_date_raw'], 'September 17, 2026 2:00pm')

    def test_refresh_is_not_a_schedule_change(self):
        previous = self.parse(entry('753'))[0]
        current = self.parse(entry('753'))[0]
        stamp_refresh(current, previous, '2026-09-07T12:00:00Z')
        self.assertFalse(current['change_labels'])
        revised = self.parse(entry('753', 'September 8, 2026'))[0]
        stamp_refresh(revised, current, '2026-09-08T12:00:00Z')
        self.assertIn('Meeting or question deadline changed', revised['change_labels'])

    def test_detail_render_and_passed_state(self):
        from app import main
        from app.core import milestones
        real_past = milestones.deadline_is_past
        with patch.object(milestones, 'deadline_is_past', side_effect=lambda r: real_past(r, datetime(2026, 9, 7, tzinfo=timezone.utc))):
            record = main.enrich(self.parse(entry('753'))[0])
        self.assertTrue(all(x['past'] for x in record['milestones_display']))
        with main.app.test_request_context('/'):
            record['published_addenda'] = [{'title': 'Addendum No. 1', 'url': 'https://www.drjtbc.org/addendum.pdf'}]
            html = main.render_template('opportunity_detail.html', opp=record,
                seo_title=record['title'], seo_description='', canonical_url='https://example.com',
                site_url='https://example.com', related=[], readiness=[])
        self.assertIn('Published date has passed.', html)
        self.assertIn('Question deadline', html)
        self.assertIn('time not published', html)
        self.assertIn('current/#753', html)
        self.assertIn('addendum contents are not automatically reconciled', html)
        self.assertIn('https://www.drjtbc.org/addendum.pdf', html)


if __name__ == '__main__':
    unittest.main()
