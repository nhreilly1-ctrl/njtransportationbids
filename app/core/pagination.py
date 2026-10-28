"""Page an already ordered feed while retaining every active filter."""
from flask import request, url_for


def paginate(records, per_page=25):
    pages = max(1, (len(records) + per_page - 1) // per_page)
    page = min(max(1, request.args.get('page', 1, type=int) or 1), pages)
    arguments = request.args.to_dict()
    def link(number):
        return url_for(request.endpoint, **dict(arguments, page=number))
    return records[(page - 1) * per_page:page * per_page], dict(
        page=page, pages=pages, total=len(records),
        start=(page - 1) * per_page + 1 if records else 0,
        end=min(page * per_page, len(records)),
        previous=link(page - 1) if page > 1 else None,
        next=link(page + 1) if page < pages else None,
    )
