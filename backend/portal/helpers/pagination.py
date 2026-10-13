from flask import request


def page_args(default=20, maximum=100):
    page = max(request.args.get('page', 1, type=int), 1)
    per_page = min(max(request.args.get('per_page', default, type=int), 1), maximum)
    return page, per_page


def paged(query, serialize, default=20, maximum=100):
    page, per_page = page_args(default, maximum)
    p = query.paginate(page=page, per_page=per_page, error_out=False)
    return {'items': [serialize(x) for x in p.items], 'page': page, 'pages': p.pages,
            'per_page': per_page, 'total': p.total}
