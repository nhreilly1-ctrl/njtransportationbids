"""Compare successful PDF fingerprints without treating outages as changes."""


def reconcile_documents(record, previous, checked_at):
    if 'document_checks' not in record:
        return False
    old = {d['url']: d for d in (previous or {}).get('document_checks', [])}
    changed = False
    for document in record['document_checks']:
        baseline = old.get(document['url'], {})
        document['checked_at'] = checked_at
        for field in ('changed_at', 'previous_sha256'):
            if baseline.get(field):
                document[field] = baseline[field]
        if document.get('state') == 'ok' and document.get('sha256'):
            document['last_successful_check'] = checked_at
            if baseline.get('sha256') and baseline['sha256'] != document['sha256']:
                document['previous_sha256'] = baseline['sha256']
                document['changed_at'] = checked_at
                changed = True
        else:
            for field in ('sha256', 'last_successful_check'):
                if baseline.get(field):
                    document[field] = baseline[field]
    record['document_change_detected'] = any(d.get('changed_at') for d in record['document_checks'])
    record['document_check_unavailable'] = any(d.get('state') != 'ok' for d in record['document_checks'])
    return changed
