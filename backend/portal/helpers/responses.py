"""Consistent JSON envelope (same shape as StockVerse): {bool, status, response}
— with the real HTTP status code set on the Response as well.

Return a single Response object (not a tuple): flask-restx would try to
JSON-serialise a (Response, code) tuple."""

from flask import jsonify


def _respond(success, body, status):
    resp = jsonify(bool=success, status=status, response=body)
    resp.status_code = status
    return resp


def ok(data=None, status=200):
    return _respond(True, data if data is not None else {}, status)


def fail(message, status=400, code=None, **extra):
    body = {'message': message}
    if code:
        body['code'] = code
    body.update(extra)
    return _respond(False, body, status)


def server_error(logger, context):
    """Log the real exception server-side; return a generic message to the client."""
    logger.exception(f'[{context}] unhandled error')
    return fail('Something went wrong. Please try again.', 500, code='SERVER_ERROR')
