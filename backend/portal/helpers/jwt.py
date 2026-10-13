from flask import jsonify
from flask_jwt_extended import JWTManager

jwt_manager = JWTManager()


class Token:
    """Short-lived access tokens only. Long-lived sessions use the opaque,
    rotating refresh cookie handled in helpers/auth.py."""

    def __init__(self, app):
        jwt_manager.init_app(app)

        def _unauth(message, code):
            return jsonify(bool=False, status=401, response={'message': message, 'code': code}), 401

        @jwt_manager.expired_token_loader
        def _expired(jwt_header, jwt_payload):
            return _unauth('Session token expired.', 'TOKEN_EXPIRED')

        @jwt_manager.invalid_token_loader
        def _invalid(error):
            return _unauth('Invalid session. Please sign in again.', 'TOKEN_INVALID')

        @jwt_manager.unauthorized_loader
        def _missing(error):
            return _unauth('Please sign in to continue.', 'AUTH_REQUIRED')
