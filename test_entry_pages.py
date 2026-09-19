"""Entry pages keep useful onward paths without weakening source evidence."""
from copy import deepcopy
from datetime import date
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from bs4 import BeautifulSoup
import app.main as main
from app.core.project_presentation import project_presentation


def record(id='entry-test', **changes):
    title = ('Route 94 bridge improvements, Contract No. 123456789, Sussex County; '
             'Federal Project No: 123, UPC No: 456, DP No: 26121.')
    return {'id': id, '_canonical_notice': True, 'title': title,
            'source_id': 'state-njdot-construction', 'source_name': 'NJDOT',
            'notice_type': 'construction', 'status': 'open', 'contract_number': '123456789',
            'official_url': 'https://dot.nj.gov/notice.pdf',
            'due_date_raw': '12/20/2099', **changes}


class EntryPageTests(unittest.TestCase):
    def render(self, path, records):
        with patch.object(main, 'load_public_opps', return_value=records):
            response = main.app.test_client().get(path)
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.data, 'html.parser')

    def test_short_heading_preserves_scope_and_never_mutates_source(self):
        item = record()
        original = deepcopy(item)
        result = project_presentation(item)
        self.assertIn('Contract No. 123456789, Sussex County', result['heading'])
        self.assertNotIn('UPC No', result['heading'])
        self.assertEqual(item, original)

    def test_other_sources_and_unique_summaries_remain_untouched(self):
        item = record(source_id='state-njta', notice_excerpt='Mandatory meeting at 10 AM.')
        result = project_presentation(item)
        self.assertEqual(result['heading'], item['title'])
        self.assertFalse(result['repeated_summary'])

    def test_full_source_and_seo_identifiers_retained(self):
        item = record()
        item['notice_excerpt'] = 'NJDOT construction contract. ' + item['title']
        soup = self.render('/opportunities/entry-test', [item])
        self.assertNotIn('UPC No', soup.h1.get_text())
        self.assertIn(item['title'], soup.select_one('.source-description').get_text())
        self.assertNotIn('open', soup.select_one('.source-description').attrs)
        self.assertIn('26121', soup.title.get_text())

    def test_section_links_have_targets_and_related_path_is_source_specific(self):
        soup = self.render('/opportunities/entry-test', [record(), record('sibling')])
        for link in soup.select('.project-sections a'):
            self.assertIsNotNone(soup.select_one(link['href']))
        query = parse_qs(urlsplit(soup.select_one('.project-browse-link')['href']).query)
        self.assertEqual(query, {'source': ['state-njdot-construction'], 'status': ['active']})
        self.assertIn('Open for bid', soup.select_one('#related-opportunities').get_text())

    def test_forecast_is_not_promoted_to_an_open_construction_bid(self):
        item = record(status='upcoming', notice_type='professional_services',
                      source_id='state-njdot-profserv-upcoming', due_date_raw='Fall 2099')
        soup = self.render('/opportunities/entry-test', [item, record('sibling')])
        self.assertIn('Upcoming', soup.select_one('.project-hero').get_text())
        self.assertIsNone(soup.select_one('[data-analytics-event="calendar_add"]'))

    def test_later_open_bids_are_not_labeled_as_unadvertised_forecasts(self):
        with patch.object(main, 'eastern_today', return_value=date(2099, 10, 1)):
            soup = self.render('/bids/construction?sort=closing', [record()])
        self.assertIn('Open bids closing later', soup.get_text())
        self.assertNotIn('Upcoming or planned; not yet open for bid', soup.get_text())

    def test_conflicting_past_deadline_never_gets_urgent_styling(self):
        item = record(source_id='state-njta', source_status='open',
                      source_status_authoritative=True, due_date_raw='01/01/2020')
        soup = self.render('/bids/construction?sort=closing', [item])
        self.assertFalse(soup.select('.soon, .soon-due'))
        self.assertIn('deadline needs confirmation', soup.get_text())

    def test_home_search_is_public_get_form_and_tracks_submission_only(self):
        soup = self.render('/', [record()])
        form = soup.select_one('form.home-search')
        self.assertEqual(form['method'], 'get')
        self.assertEqual(form['action'], '/notices')
        self.assertEqual(form.select_one('[name="status"]')['value'], 'active')
        self.assertEqual(form['data-analytics-event'], 'filter_applied')
        self.assertIsNotNone(form.select_one('label[for="home-query"]'))


if __name__ == '__main__':
    unittest.main()
