import unittest
from unittest.mock import patch

from app import main as app_main
from app.core.bid_readiness import readiness_for
from app.core.relatedness import rank_related, score_related


def rec(**kw):
    base = {"id": "r1", "source_id": "state-njdot-construction", "record_type": "construction",
            "title": "Bridge work", "status": "open"}
    base.update(kw)
    return base


class BidReadinessTests(unittest.TestCase):
    def _titles(self, pack):
        return [item["title"] for item in pack["resources"]]

    def test_njdot_construction_routes_njdot_prequalification_and_specs(self):
        pack = readiness_for(rec())
        self.assertEqual(pack["label"], "NJDOT")
        self.assertIn("NJDOT Construction Prequalification", self._titles(pack))
        self.assertIn("NJDOT Standard Specifications", self._titles(pack))

    def test_njdot_professional_services_routes_consultant_track_not_construction(self):
        pack = readiness_for(rec(record_type="professional_services", source_id="state-njdot-profserv"))
        titles = self._titles(pack)
        self.assertIn("NJDOT Consultant Prequalification and Cost Basis Approval", titles)
        self.assertNotIn("NJDOT Construction Prequalification", titles)

    def test_turnpike_track_is_separate_from_njdot(self):
        pack = readiness_for(rec(source_id="state-njta"))
        titles = self._titles(pack)
        self.assertIn("NJTA Construction and Maintenance Resources", titles)
        self.assertNotIn("NJDOT Construction Prequalification", titles)

    def test_bistate_records_lead_with_authority_resources_not_state_shortcuts(self):
        # Agency identity alone is not evidence that a generic New Jersey
        # registration, wage, or surety resource controls the solicitation.
        for source_id in ("state-panynj", "state-drpa", "state-drjtbc-construction"):
            with self.subTest(source_id=source_id):
                pack = readiness_for(rec(source_id=source_id))
                titles = self._titles(pack)
                self.assertTrue(pack["caveat"])
                for withheld in ("NJ Business Registration Certificate",
                                 "Public Works Contractor Registration",
                                 "NJ Prevailing Wage Determinations",
                                 "NJ Approved Surety Companies"):
                    self.assertNotIn(withheld, titles)

    def test_local_work_routes_local_public_contracts_law_and_nj_baseline(self):
        pack = readiness_for(rec(source_id="county-morris"))
        titles = self._titles(pack)
        self.assertIn("NJ Local Agency Procurement Laws and Standard Bid Forms", titles)
        self.assertIn("Public Works Contractor Registration", titles)
        self.assertFalse(pack["caveat"])

    def test_federal_language_adds_federal_aid_references(self):
        plain = self._titles(readiness_for(rec(title="County bridge deck repair")))
        federal = self._titles(readiness_for(rec(title="Federal-aid bridge deck repair")))
        self.assertNotIn("Federal Wage Determinations", plain)
        self.assertIn("Federal Wage Determinations", federal)

    def test_stated_state_funding_outranks_a_stray_federal_mention(self):
        # NJDOT publishes "Funding: State." / "Funding: Federal." on anticipated
        # records; the stated field must beat any incidental use of the word.
        state_funded = rec(notice_excerpt="Expected posting: Fall 2026. Funding: State. "
                                          "Coordinate with the federal highway program office.")
        self.assertNotIn("Federal Wage Determinations", self._titles(readiness_for(state_funded)))

        federal_funded = rec(notice_excerpt="Expected posting: Fall 2026. Funding: Federal.")
        self.assertIn("Federal Wage Determinations", self._titles(readiness_for(federal_funded)))

    def test_federal_project_number_counts_as_federal_aid(self):
        record = rec(notice_excerpt="Warren County, Federal Project No: 0022361, UPC No: 263080")
        self.assertIn("FHWA Buy America and BABA Guidance", self._titles(readiness_for(record)))

    def test_federal_njdot_pack_keeps_state_readiness_and_full_federal_set(self):
        pack = readiness_for(rec(notice_excerpt="Funding: Federal."))
        titles = self._titles(pack)
        for required in (
            "NJ Business Registration Certificate",
            "Public Works Contractor Registration",
            "NJ Prevailing Wage Determinations",
            "Federal Wage Determinations",
            "FHWA Buy America and BABA Guidance",
            "NJ Unified Certification Program - DBE",
        ):
            self.assertIn(required, titles)
        self.assertLessEqual(len(titles), 8)

    def test_njtransit_federal_resources_require_notice_evidence(self):
        plain = readiness_for(rec(source_id="state-njtransit", title="Station rehabilitation"))
        federal = readiness_for(rec(
            source_id="state-njtransit",
            title="Station rehabilitation",
            notice_excerpt="Funding: Federal.",
        ))
        self.assertNotIn("Federal Wage Determinations", self._titles(plain))
        self.assertFalse(plain["federal_evidence"])
        self.assertIn("Federal Wage Determinations", self._titles(federal))
        self.assertTrue(federal["federal_evidence"])

    def test_professional_services_federal_pack_omits_construction_compliance(self):
        pack = readiness_for(rec(
            source_id="state-njdot-profserv",
            record_type="professional_services",
            notice_excerpt="Funding: Federal.",
        ))
        titles = self._titles(pack)
        self.assertIn("NJ Unified Certification Program - DBE", titles)
        self.assertNotIn("Federal Wage Determinations", titles)
        self.assertNotIn("FHWA Buy America and BABA Guidance", titles)

    def test_unknown_record_type_does_not_guess_a_construction_pack(self):
        self.assertIsNone(readiness_for(rec(record_type="", notice_type="public_notice")))

    def test_every_routed_item_comes_from_the_catalog_unchanged(self):
        from app.resource_catalog import RESOURCE_SECTIONS
        known = {r["title"]: r for s in RESOURCE_SECTIONS for r in s["resources"]}
        for source_id in ("state-njdot-construction", "state-njta", "state-panynj",
                          "county-morris", "state-njtransit", "state-njtpa"):
            pack = readiness_for(rec(source_id=source_id))
            for item in pack["resources"]:
                self.assertIn(item["title"], known)
                self.assertEqual(item["url"], known[item["title"]]["url"])
                self.assertEqual(item["use_when"], known[item["title"]]["use_when"])

    def test_unknown_source_still_returns_a_usable_track(self):
        pack = readiness_for(rec(source_id="state-mystery"))
        self.assertIsNotNone(pack)
        self.assertNotIn("NJSTART Vendor Registration", self._titles(pack))

    def test_njstart_registration_requires_platform_evidence(self):
        pack = readiness_for(rec(
            source_id="state-mystery",
            platform="NJSTART",
            official_url="https://www.njstart.gov/bso/",
        ))
        self.assertEqual(self._titles(pack)[0], "NJSTART Vendor Registration")


class RelatednessTests(unittest.TestCase):
    def test_shared_corridor_outranks_same_agency(self):
        subject = rec(id="a", corridors=["I-287"], counties=["Morris"])
        corridor_match = rec(id="b", source_id="county-morris", corridors=["I-287"])
        agency_match = rec(id="c", corridors=[], counties=[])
        ranked = rank_related(subject, [corridor_match, agency_match])
        self.assertEqual(ranked[0]["id"], "b")
        self.assertEqual(ranked[0]["relation_reason"], "Also on I-287")

    def test_shared_county_beats_agency_only(self):
        subject = rec(id="a", counties=["Monmouth"])
        county_match = rec(id="b", source_id="county-monmouth", counties=["Monmouth"])
        agency_only = rec(id="c")
        ranked = rank_related(subject, [county_match, agency_only])
        self.assertEqual(ranked[0]["id"], "b")
        self.assertIn("Monmouth", ranked[0]["relation_reason"])

    def test_exact_crossing_and_named_road_outrank_broader_matches(self):
        subject = rec(
            id="a",
            crossing_phrases=["Bridge over Raritan River"],
            road_names=["Spring Valley Road"],
            corridors=["US-1"],
            counties=["Middlesex"],
            structure_types=["bridge"],
        )
        crossing = rec(id="crossing", source_id="x", record_type="professional_services",
                       crossing_phrases=["bridge over raritan river"])
        road = rec(id="road", source_id="x", record_type="professional_services",
                   road_names=["Spring Valley Road"], corridors=["US-1"],
                   counties=["Middlesex"], structure_types=["bridge"])
        ranked = rank_related(subject, [road, crossing])
        self.assertEqual([item["id"] for item in ranked], ["crossing", "road"])
        self.assertEqual(ranked[0]["relation_reason"], "Same crossing: Bridge over Raritan River")

    def test_corridor_match_cannot_be_outscored_by_combined_lower_tiers(self):
        subject = rec(id="a", source_id="state-njdot-construction", record_type="construction",
                      corridors=["I-287"], counties=["Morris"], structure_types=["bridge"])
        corridor_only = rec(id="corridor", source_id="county-somerset",
                            record_type="professional_services", corridors=["I-287"])
        lower_tiers = rec(id="lower", source_id="state-njdot-construction",
                          record_type="construction", counties=["Morris"],
                          structure_types=["bridge"])
        self.assertEqual(rank_related(subject, [lower_tiers, corridor_only])[0]["id"], "corridor")

    def test_expired_and_self_are_excluded(self):
        subject = rec(id="a", corridors=["US-1"])
        ranked = rank_related(subject, [subject, rec(id="b", corridors=["US-1"], status="expired")])
        self.assertEqual(ranked, [])

    def test_structure_overlap_is_labelled(self):
        subject = rec(id="a", source_id="x", record_type="construction", structure_types=["bridge"])
        other = rec(id="b", source_id="y", record_type="construction", structure_types=["bridge"])
        ranked = rank_related(subject, [other])
        self.assertEqual(ranked[0]["relation_reason"], "Also bridge work")

    def test_ties_prefer_the_sooner_deadline(self):
        subject = rec(id="a", corridors=["I-78"])
        late = rec(id="late", corridors=["I-78"], due_date_parsed="2099-12-31")
        soon = rec(id="soon", corridors=["I-78"], due_date_parsed="2026-09-01")
        self.assertEqual([r["id"] for r in rank_related(subject, [late, soon])], ["soon", "late"])

    def test_score_is_zero_for_wholly_unrelated_records(self):
        subject = rec(id="a", source_id="x", record_type="construction")
        other = rec(id="b", source_id="y", record_type="professional_services")
        self.assertEqual(score_related(subject, other)[0], 0)

    def test_same_type_alone_is_not_a_relationship(self):
        subject = rec(id="a", source_id="x", record_type="construction")
        other = rec(id="b", source_id="y", record_type="construction")
        self.assertEqual(score_related(subject, other), (0, ""))
        self.assertEqual(rank_related(subject, [other]), [])


class DetailPageTests(unittest.TestCase):
    def test_detail_page_renders_reasons_readiness_and_pitch(self):
        subject = {
            "id": "subject", "_canonical_notice": True, "title": "Route 1 NB Bridge over Raritan River",
            "status": "open", "source_status": "open", "source_id": "state-njdot-construction",
            "source_name": "NJDOT Construction Services", "source_tier": "state",
            "source_url": "https://agency.example/b", "official_url": "https://agency.example/b/1",
            "county": "", "notice_type": "construction", "notice_subtype": "construction",
            "due_date_raw": "12/31/68", "contract_number": "T-1", "access_type": "Public access",
            "platform": "Agency website", "crawled_at": "2026-08-29T12:00:00+00:00",
        }
        sibling = dict(subject, id="sibling", title="Route 1 resurfacing, Middlesex County",
                       contract_number="T-2")
        with patch.object(app_main, "load_public_opps", return_value=[subject, sibling]):
            html = app_main.app.test_client().get("/opportunities/subject").get_data(as_text=True)

        self.assertIn("Related opportunities", html)
        self.assertIn("Also on US-1", html)
        self.assertIn("Bid resources for NJDOT", html)
        self.assertIn("NJDOT Construction Prequalification", html)
        self.assertIn("official New Jersey agency sources", html)

    def test_hero_leads_with_evidenced_location_not_a_county_disclaimer(self):
        # docs/TIME_AND_TOOLS.md rule 2: the strongest location evidence answers
        # "where" above the fold. A notice naming the NJ Turnpike must not read
        # "County not stated in notice" just because no county was extracted.
        subject = {
            "id": "tpk", "_canonical_notice": True,
            "title": "Contract No. A200.915-1 Traffic Signals on the New Jersey Turnpike",
            "status": "open", "source_status": "open", "source_id": "state-njta",
            "source_name": "NJ Turnpike Authority", "source_tier": "state",
            "source_url": "https://agency.example/b", "official_url": "https://agency.example/b/1",
            "county": "", "notice_type": "construction", "notice_subtype": "construction",
            "due_date_raw": "12/31/68", "contract_number": "A200.915-1",
            "access_type": "Public access", "platform": "Agency website",
            "crawled_at": "2026-08-29T12:00:00+00:00",
        }
        with patch.object(app_main, "load_public_opps", return_value=[subject]):
            html = app_main.app.test_client().get("/opportunities/tpk").get_data(as_text=True)
        hero = html.split('class="opportunity-hero"', 1)[1].split("</h1>", 1)[1][:300]
        self.assertIn("NJ Turnpike", hero)
        self.assertNotIn("County not stated in notice", hero)

    def test_hero_keeps_the_scope_label_alongside_the_corridor(self):
        subject = {
            "id": "bs", "_canonical_notice": True,
            "title": "Professional engineering services, I-78 and I-80 corridors",
            "status": "open", "source_status": "open", "source_id": "state-drjtbc-profserv",
            "source_name": "DRJTBC", "source_tier": "state",
            "source_url": "https://agency.example/b", "official_url": "https://agency.example/b/1",
            "county": "", "notice_type": "professional_services",
            "notice_subtype": "professional_services", "due_date_raw": "12/31/68",
            "contract_number": "X-1", "access_type": "Public access",
            "platform": "Agency website", "crawled_at": "2026-08-29T12:00:00+00:00",
        }
        with patch.object(app_main, "load_public_opps", return_value=[subject]):
            html = app_main.app.test_client().get("/opportunities/bs").get_data(as_text=True)
        hero = html.split('class="opportunity-hero"', 1)[1].split("</h1>", 1)[1][:300]
        self.assertIn("I-78", hero)
        self.assertIn("Bi-state", hero)

    def test_bistate_detail_page_shows_the_different_rulebook_warning(self):
        subject = {
            "id": "pa", "_canonical_notice": True, "title": "George Washington Bridge deck sections",
            "status": "open", "source_status": "open", "source_id": "state-panynj",
            "source_name": "Port Authority NY/NJ", "source_tier": "state",
            "source_url": "https://agency.example/b", "official_url": "https://agency.example/b/1",
            "county": "", "notice_type": "construction", "notice_subtype": "construction",
            "due_date_raw": "12/31/68", "contract_number": "GWB-1", "access_type": "Public access",
            "platform": "Agency website", "crawled_at": "2026-08-29T12:00:00+00:00",
        }
        with patch.object(app_main, "load_public_opps", return_value=[subject]):
            html = app_main.app.test_client().get("/opportunities/pa").get_data(as_text=True)
        self.assertIn("Different rulebook", html)
        self.assertIn("official bid documents control", html)
        self.assertNotIn("do not apply", html)
        self.assertNotIn("publicworksregistration.shtml", html)
        self.assertNotIn("busregcert.shtml", html)


if __name__ == "__main__":
    unittest.main()
