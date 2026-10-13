"""Notifications, device bindings, login history and per-user security
preferences — small helpers shared by the auth, bills and support routes."""

import hashlib
import re

from flask import current_app, request

from portal import db
from portal.models.base import utcnow
from portal.models.device_bindings import DeviceBindings
from portal.models.login_history import LoginHistory
from portal.models.notifications import Notifications, NotificationType
from portal.models.user_security_settings import UserSecuritySettings

DEVICE_HEADER = 'X-Device-Id'
_DEVICE_RE = re.compile(r'^[A-Za-z0-9_-]{16,64}$')


# ── Security preferences ────────────────────────────────────────────────────

def security_prefs(user_id):
    """Existing row or an unsaved default (all alerts on, server idle lock)."""
    return (UserSecuritySettings.query.filter_by(user_id=user_id).first()
            or UserSecuritySettings(user_id=user_id, login_alerts=True, payment_alerts=True))


def idle_minutes_for(user_id):
    server = current_app.config['SESSION_IDLE_LOCK_MINUTES']
    pref = security_prefs(user_id).idle_lock_minutes
    return min(server, pref) if pref else server


# ── Notifications ───────────────────────────────────────────────────────────

def notify(user_id, ntype, title, body=None, link=None, dedupe_key=None):
    """Queue an in-app notification on the current session (caller commits).
    Respects the user's payment/login alert preferences. Idempotent per dedupe_key."""
    prefs = security_prefs(user_id)
    if ntype == NotificationType.PAYMENT and not prefs.payment_alerts:
        return None
    if ntype == NotificationType.SECURITY and title.startswith('New device') and not prefs.login_alerts:
        return None
    if dedupe_key and Notifications.query.filter_by(dedupe_key=dedupe_key[:120]).first():
        return None
    n = Notifications(user_id=user_id, type=ntype, title=title[:120], body=(body or '')[:500] or None,
                      link=link, dedupe_key=dedupe_key[:120] if dedupe_key else None)
    db.session.add(n)
    return n


# ── Devices ─────────────────────────────────────────────────────────────────

def _device_name(ua):
    ua = ua or ''
    os_ = ('Android' if 'Android' in ua else 'iPhone' if 'iPhone' in ua else 'iPad' if 'iPad' in ua
           else 'Windows' if 'Windows' in ua else 'Mac' if 'Mac OS' in ua else 'Linux' if 'Linux' in ua else 'Device')
    br = ('Edge' if 'Edg/' in ua else 'Chrome' if 'Chrome/' in ua else 'Firefox' if 'Firefox/' in ua
          else 'Safari' if 'Safari/' in ua else 'Browser')
    return f'{br} on {os_}'


def bind_device(user):
    """Upsert the device from the X-Device-Id header. Returns (binding, is_new) or (None, False)
    when the client sent no valid id. Only a SHA-256 of the id is stored."""
    raw = request.headers.get(DEVICE_HEADER, '')
    if not _DEVICE_RE.match(raw):
        return None, False
    h = hashlib.sha256(f'{user.user_id}:{raw}'.encode()).hexdigest()
    b = DeviceBindings.query.filter_by(user_id=user.user_id, device_hash=h).first()
    is_new = b is None
    if is_new:
        b = DeviceBindings(user_id=user.user_id, device_hash=h,
                           device_name=_device_name(request.headers.get('User-Agent')))
        db.session.add(b)
    b.last_seen_at = utcnow()
    b.last_ip = (request.remote_addr or '')[:64]
    b.revoked_at = None
    db.session.flush()
    return b, is_new


# ── Login history ───────────────────────────────────────────────────────────

def log_login(user_id, event, status, reason=None, session=None, device=None):
    db.session.add(LoginHistory(
        user_id=user_id, event=event, status=status, failure_reason=(reason or '')[:60] or None,
        session_id=session.session_id if session is not None else None,
        device_binding_id=device.device_binding_id if device is not None else None,
        ip_address=(request.remote_addr or '')[:64],
        user_agent=(request.headers.get('User-Agent') or '')[:255]))
