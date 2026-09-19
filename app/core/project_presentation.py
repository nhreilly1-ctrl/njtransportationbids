"""Presentation-only reductions; source titles and identifiers remain intact."""
import re


def project_presentation(record):
    title = record.get('title') or ''
    heading = title
    if record.get('source_id') == 'state-njdot-construction':
        # Only remove the trailing administrative identifiers, not project scope.
        heading = re.split(r';\s*(?:Federal Project No\s*:|100% State Funded\b)',
                           title, maxsplit=1, flags=re.I)[0].rstrip(' ,;')
    excerpt = ' '.join((record.get('notice_excerpt') or '').split())
    normalized = ' '.join(title.split())
    repeated_summary = bool(normalized and excerpt in (
        normalized, 'NJDOT construction contract. ' + normalized))
    return {'heading': heading, 'shortened': heading != title,
            'repeated_summary': repeated_summary}
