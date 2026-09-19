"""Research links remain context, not inferred project facts or conditions."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.core.project_research import research_for, TOOLS


def record(title="Route 94 resurfacing", **changes):
    return {"id": "research-test", "_canonical_notice": True,
            "source_id": "state-njdot-construction", "source_name": "NJDOT",
            "title": title, "notice_type": "construction", "status": "open",
            "official_url": "https://dot.nj.gov/notice.pdf",
            "due_date_raw": "12/20/2099", **changes}


def keys(pack):
    return [g["key"] for g in pack["groups"]]


class ProjectResearchTests(unittest.TestCase):
    def test_paving_has_four_groups_and_camera_directory(self):
        pack = research_for(record())
        self.assertEqual(keys(pack), ["road", "traffic", "prices", "index"])
        camera = pack["groups"][0]["links"][1]
        self.assertEqual(camera["url"], "https://511nj.org/camera")
        self.assertEqual(camera["label"], "Browse public traffic cameras")
        self.assertIn("has not been verified", pack["groups"][0]["description"])

    def test_bridge_and_drainage_context(self):
        for title in ("Route 28 bridge replacement", "Drainage restoration I-278, I-280, I-287"):
            with self.subTest(title=title):
                self.assertEqual(keys(research_for(record(title))), ["road", "borings", "environment"])

    def test_verified_background_is_reused_not_guessed(self):
        pack = research_for(record("Rt 1 NB, Bridge over Raritan River"))
        self.assertEqual(keys(pack), ["background", "road", "borings", "environment"])
        self.assertIn("Morris Goodkind", pack["groups"][0]["description"])
        wrong = research_for(record("Rt 1 SB, Bridge over Raritan River"))
        self.assertNotIn("background", keys(wrong))

    def test_professional_track_wins_over_paving_words(self):
        pack = research_for(record("Pavement Preservation North Contract 13",
                                  source_id="state-njdot-profserv-upcoming",
                                  notice_type="professional_services", status="upcoming"))
        self.assertIn("consultant", keys(pack))
        self.assertNotIn("prices", keys(pack))
        self.assertNotIn("index", keys(pack))

    def test_professional_bridge_has_bounded_tools(self):
        pack = research_for(record("Rt 1 NB, Bridge over Raritan River",
                                  source_id="state-njdot-profserv-upcoming",
                                  record_type="professional_services", status="upcoming"))
        self.assertEqual(keys(pack), ["consultant", "background", "road", "borings"])

    def test_general_professional_notice_is_not_given_a_fake_site(self):
        pack = research_for(record("Statewide Surveying Services Term Agreement",
                                  notice_type="professional_services"))
        self.assertEqual(keys(pack), ["consultant"])
        self.assertEqual(pack["context"], "")

    def test_nonpilot_sources_types_and_hidden_records(self):
        for source in ("county-morris", "state-njta", "state-njdot-notices", "state-njdot-fake", None):
            self.assertIsNone(research_for(record(source_id=source)))
        for status in ("noise", "deleted"):
            self.assertIsNone(research_for(record(status=status)))
        self.assertIsNone(research_for(record(notice_type="public_notice")))

    def test_no_body_office_or_unrelated_title_matches(self):
        self.assertIsNone(research_for(record("Equipment supply", notice_excerpt="Route 1 bridge and asphalt office")))
        self.assertIsNone(research_for(record("Cambridge equipment")))

    def test_multiple_routes_retained_and_record_not_mutated(self):
        item = record("Drainage restoration I-278, I-280, I-287", counties=["Bergen", "Essex"])
        original = deepcopy(item)
        pack = research_for(item)
        for route in ("I-278", "I-280", "I-287"):
            self.assertIn(route, pack["context"])
        self.assertEqual(item, original)
        self.assertNotIn("Bergen", str(pack))
        self.assertNotIn("lat", str([link["url"] for g in pack["groups"] for link in g["links"]]))

    def test_no_forecast_or_meeting_calendar_from_bid_date(self):
        pack = research_for(record())
        self.assertNotIn("weather.gov", str(pack))
        self.assertNotIn("calendar", str(pack))

    def test_links_use_official_https_hosts(self):
        for tool in TOOLS.values():
            for link in tool["links"]:
                url = urlsplit(link["url"])
                self.assertEqual(url.scheme, "https")
                self.assertIn(url.hostname, ("dot.nj.gov", "dep.nj.gov", "511nj.org"))

    def test_mixed_scope_is_bounded_and_uses_site_context(self):
        pack = research_for(record("Route 1 bridge replacement and resurfacing"))
        self.assertEqual(keys(pack), ["road", "borings", "environment"])

    def test_reference_only_links_available_on_closed_project(self):
        self.assertEqual(keys(research_for(record(status="expired"))), ["road", "traffic", "prices", "index"])

    def render(self, item):
        import app.main as main
        with patch.object(main, "load_public_opps", return_value=[item]):
            response = main.app.test_client().get("/opportunities/research-test")
        self.assertEqual(response.status_code, 200)
        return BeautifulSoup(response.data, "html.parser")

    def test_detail_placement_tracking_and_no_embeds(self):
        soup = self.render(record())
        research = soup.select_one("#project-research")
        self.assertIsNotNone(research)
        self.assertEqual(len(research.select("article")), 4)
        links = research.select('[data-analytics-event="project_research_click"]')
        self.assertEqual(len(links), 5)
        self.assertTrue(all(x["data-notice-id"] == "research-test" for x in links))
        self.assertFalse(research.select("iframe, img, video, script"))
        html = str(soup)
        self.assertLess(html.index('id="project-maps"'), html.index('id="project-research"'))
        self.assertLess(html.index('id="agency-preparation-heading"'), html.index('id="project-research"'))
        self.assertLess(html.index('id="project-research"'), html.index('class="project-record-details"'))
        self.assertEqual(len(soup.select("#agency-preparation-heading")), 1)
        self.assertNotIn("open", soup.select_one("details.project-record-details").attrs)
        self.assertTrue(soup.select_one('[data-analytics-event="official_source_click"]'))
        self.assertTrue(soup.select_one('[data-analytics-event="calendar_add"]'))

    def test_other_agency_retains_original_layout(self):
        soup = self.render(record(source_id="county-morris"))
        self.assertIsNone(soup.select_one("#project-research"))
        self.assertIsNone(soup.select_one("details.project-record-details"))
        self.assertIn("Next step", soup.get_text())
        self.assertEqual(len(soup.select("#agency-preparation-heading")), 1)

    def test_conflicting_deadline_still_has_no_calendar(self):
        soup = self.render(record(deadline_conflict=True, due_date_raw="01/01/2020"))
        self.assertIsNone(soup.select_one('[data-analytics-event="calendar_add"]'))


if __name__ == "__main__":
    unittest.main()
