"""Agency intelligence built from reviewed preparation content, not guessed rules."""

from app.core.agency_preparation import preparation_for

_PROFILES = (
    ("njdot", "NJDOT", "Separate construction, consultant and design-build paths",
     (("state-njdot-construction", "Construction"), ("state-njdot-profserv", "Professional services"),
      ("state-njdot-profserv-upcoming", "Anticipated consultant work"), ("state-njdot-design-build", "Design-build")),
     (("state-njdot-construction", "construction"), ("state-njdot-profserv", "professional_services")),
     "Design-build requirements are not covered by the conventional construction or consultant guidance below.",
     ("Which work classifications or consultant disciplines does this project require?",
      "Are approvals in place, rather than merely applied for?",
      "Which submission system and special provisions does this solicitation name?")),
    ("njta", "New Jersey Turnpike Authority", "Do not carry NJDOT approval assumptions into NJTA work",
     (("state-njta", "Turnpike Authority opportunities"),),
     (("state-njta", "construction"), ("state-njta", "professional_services")),
     "Security amounts, participation targets, portal instructions and delivery requirements need project-level review.",
     ("Does the required classification or profile code match the firm's current approval?",
      "Which financial-statement basis determines consultant approval validity?",
      "What bid security, participation documentation and delivery method does this package require?")),
    ("drjtbc", "Delaware River Joint Toll Bridge Commission", "Read the solicitation and every addendum together",
     (("state-drjtbc-construction", "Construction"), ("state-drjtbc-profserv", "Professional services")), (),
     "Agency-wide qualification and submission rules have not been verified. Do not apply the example below to other contracts.",
     ("Has an addendum changed delivery, copies or required acknowledgments?",
      "Are technical and fee submissions separated as the project requires?",
      "What attendance, qualification and question-deadline requirements are stated in this RFP?")),
    ("ocean", "Ocean County", "Start with the current OpenGov project, not an award archive",
     (("county-ocean", "Ocean County opportunities"),), (("county-ocean", "construction"),),
     "A universal closing hour, security amount and professional-services checklist have not been verified.",
     ("Have you opened the current project rather than an older award result?",
      "Which attachments and addenda are part of this submission?",
      "Does this procurement require construction bid forms or a different proposal package?")),
    ("morris", "Morris County", "Downloading documents is not the same as submitting a bid",
     (("county-morris", "Morris County opportunities"),), (("county-morris", "construction"),),
     "The general purchasing guide contains legacy wording. Current delivery location, signatures, security and submission channels need package-level confirmation.",
     ("Does the current package call for physical delivery, and where must it be received?",
      "Which originals, signatures and envelope markings does it require?",
      "What opening time and addenda does the current cover sheet identify?")),
)


def guides():
    return [dict(slug=slug, name=name, orientation=orientation,
                 sources=[dict(id=source, label=label) for source, label in sources],
                 guidance=[{**preparation_for(dict(source_id=source, notice_type=kind)),
                            "audience": ("Construction" if kind == "construction" else "Professional services")
                            if source.startswith("state-") else "Procurement orientation"}
                           for source, kind in tracks], gap=gap, questions=questions)
            for slug, name, orientation, sources, tracks, gap, questions in _PROFILES]


def guide_slug_for(record):
    source = record.get("source_id")
    return next((slug for slug, _, _, sources, _, _, _ in _PROFILES
                 if source in {entry[0] for entry in sources}), None)
