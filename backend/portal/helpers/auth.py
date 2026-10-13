"""
Session handling and the `auth_required` guard used by every protected route.

Model
-----
* Access token: JWT, 15 min, sent as `Authorization: Bearer`, kept in memory by the SPA.
  Carries `sid` (the session's public id).
* Refresh token: 384-bit random string in an httpOnly, SameSite=Strict cookie scoped
  to /v1/authentication. Stored only as SHA-256. Rotated on every use; replaying a
  rotated token revokes the session (theft detection).
* App lock: a session idle for SESSION_IDLE_LOCK_MINUTES is LOCKED server-side —
  API calls and silent refresh are refused until the user unlocks with PIN or biometric.
"""

import hashlib
import secrets
from datetime import timedelta
from functools import wraps

from flask import current_app, g, request
from flask_jwt_extended import create_access_token, get_jwt, get_jwt_identity, verify_jwt_in_request

from portal import db
from portal.models.base import utcnow
from portal.models.users import Users, UserStatus
from portal.models.user_sessions import UserSessions, SessionStatus
from .responses import fail

CSRF_HEADER = 'X-Requested-With'
CSRF_VALUE = 'cardvault'
_ACTIVITY_WRITE_INTERVAL = timedelta(seconds=60)


def client_ip():
    # Trust X-Forwarded-For only behind a proxy you control (configure ProxyFix in PROD).
    return (request.remote_addr or '')[:64]


def hash_token(raw):
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def idle_limit():
    return timedelta(minutes=current_app.config['SESSION_IDLE_LOCK_MINUTES'])


def is_locked(session):
    # The user's own auto-lock preference can only shorten the server limit.
    from portal.helpers.activity import idle_minutes_for
    return utcnow() - session.last_active_at > timedelta(minutes=idle_minutes_for(session.user_id))


def is_usable(session):
    return (session is not None and session.status == SessionStatus.ACTIVE
            and session.expires_at > utcnow())


def create_session(user):
    """Create a device session; returns (session, raw_refresh_token)."""
    raw = secrets.token_urlsafe(48)
    s = UserSessions(
        user_id=user.user_id,
        refresh_token_hash=hash_token(raw),
        status=SessionStatus.ACTIVE,
        last_active_at=utcnow(),
        expires_at=utcnow() + timedelta(days=current_app.config['SESSION_ABSOLUTE_DAYS']),
        ip_address=client_ip(),
        user_agent=(request.headers.get('User-Agent') or '')[:255],
    )
    db.session.add(s)
    db.session.flush()
    return s, raw


def rotate_refresh(session):
    raw = secrets.token_urlsafe(48)
    session.previous_refresh_hash = session.refresh_token_hash
    session.refresh_token_hash = hash_token(raw)
    return raw


def revoke_session(session, reason):
    session.status = SessionStatus.REVOKED
    session.revoked_reason = reason[:50]


def issue_access_token(user, session):
    return create_access_token(identity=str(user.user_id), additional_claims={'sid': session.public_id})


def set_refresh_cookie(resp, raw):
    cfg = current_app.config
    resp.set_cookie(
        cfg['REFRESH_COOKIE_NAME'], raw,
        max_age=cfg['SESSION_ABSOLUTE_DAYS'] * 86400,
        httponly=True, secure=cfg['REFRESH_COOKIE_SECURE'], samesite='Strict',
        path='/v1/authentication',
    )
    return resp


def clear_refresh_cookie(resp):
    resp.delete_cookie(current_app.config['REFRESH_COOKIE_NAME'], path='/v1/authentication')
    return resp


def session_from_cookie():
    """Resolve the session from the refresh cookie. Returns (session, error_response)."""
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        return None, fail('Missing request header.', 403, code='CSRF_CHECK_FAILED')
    raw = request.cookies.get(current_app.config['REFRESH_COOKIE_NAME'])
    if not raw:
        return None, fail('No active session on this device.', 401, code='NO_SESSION')

    h = hash_token(raw)
    session = UserSessions.query.filter_by(refresh_token_hash=h).first()
    if session is None:
        reused = UserSessions.query.filter_by(previous_refresh_hash=h).first()
        if reused and reused.status == SessionStatus.ACTIVE:
            revoke_session(reused, 'REFRESH_TOKEN_REUSE')
            db.session.commit()
            current_app.logger.warning(f'[auth] refresh token reuse — session {reused.session_id} revoked')
        return None, fail('Session ended. Please sign in again.', 401, code='SESSION_ENDED')

    if not is_usable(session):
        return None, fail('Session ended. Please sign in again.', 401, code='SESSION_ENDED')
    if session.user.status != UserStatus.ACTIVE:
        return None, fail('Account is not active.', 403, code='ACCOUNT_INACTIVE')
    return session, None


def auth_required(fn):
    """JWT + live session check + idle lock. Sets g.user and g.session."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        sid = get_jwt().get('sid')
        session = UserSessions.query.filter_by(public_id=sid).first() if sid else None
        if not is_usable(session) or str(session.user_id) != get_jwt_identity():
            return fail('Session ended. Please sign in again.', 401, code='SESSION_ENDED')
        if is_locked(session):
            return fail('App locked. Unlock with your PIN.', 401, code='APP_LOCKED')
        user = session.user
        if user.status != UserStatus.ACTIVE:
            return fail('Account is not active.', 403, code='ACCOUNT_INACTIVE')

        now = utcnow()
        if now - session.last_active_at > _ACTIVITY_WRITE_INTERVAL:
            session.last_active_at = now
            db.session.commit()

        g.user, g.session = user, session
        return fn(*args, **kwargs)
    return wrapper


def current_user() -> Users:
    return g.user


def role_required(*roles):
    """auth_required + the user's role (from the DB, not the token) must be in `roles`.
    Staff roles additionally must have an app PIN set."""
    def deco(fn):
        @wraps(fn)
        @auth_required
        def wrapper(*args, **kwargs):
            from portal.models.roles import RoleName
            role = g.user.role_name
            if role not in roles:
                return fail('You do not have access to this area.', 403, code='FORBIDDEN')
            if role in RoleName.STAFF and not g.user.pin_hash:
                return fail('Set an app PIN before using staff tools.', 403, code='PIN_REQUIRED')
            if g.user.pin_reset_required:
                return fail('Set a new PIN to replace your temporary PIN.', 403, code='PIN_RESET_REQUIRED')
            return fn(*args, **kwargs)
        return wrapper
    return deco


def customer_required(fn):
    """Card, bill and payment endpoints are for customers (USER role) only."""
    from portal.models.roles import RoleName
    return role_required(RoleName.USER)(fn)
