"""Title-based browsing hints; never overwrite source types or eligibility."""
import re

WORK_FOCUS = {"projects": "Construction projects", "supplies": "Materials and parts",
              "support": "Road-support services", "professional": "Professional services",
              "unclear": "Other / unclear"}


def work_focus(record):
    title = re.sub(r"[^a-z0-9]+", " ", str(record.get("title") or "").lower())
    patterns = {
        "professional": r"\b(?:professional services|engineering services|consulting services|inspection services|construction management|construction project management|design services|surveying services|supervision of construction)\b",
        "supplies": r"\b(?:rock salt|snow plow parts|snowplow parts|cutting edges)\b",
        "support": r"\b(?:towing|snow removal|snow plowing|tree trimming|street sweeping|road sweeping|roadway sweeping)\b",
        "projects": r"\b(?:resurfacing|pavement preservation|bridge rehabilitation|bridge replacement|culvert replacement|drainage restoration)\b",
    }
    matches = {key: re.search(pattern, title) for key, pattern in patterns.items()}
    found = [key for key, match in matches.items() if match]
    if (record.get('notice_type') == 'professional_services' or record.get('notice_subtype') == 'professional_services') and found != ['professional']:
        found = []
    # Mixed scopes have no reliable primary focus.
    if len(found) != 1:
        return {"key": "unclear", "label": WORK_FOCUS["unclear"], "evidence": ""}
    key = found[0]
    return {"key": key, "label": WORK_FOCUS[key], "evidence": matches[key].group()}


def matches_work_focus(record, selected):
    return selected not in WORK_FOCUS or work_focus(record)["key"] == selected
