from flask import current_app, request

from portal import db
from portal.models.audit_logs import AuditLogs

# Keys that must never land in the audit trail even if a caller passes them.
_FORBIDDEN = {'otp', 'otp_code', 'pin', 'current_pin', 'new_pin', 'token', 'access_token',
              'refresh_token', 'signature', 'razorpay_signature', 'card_number', 'cvv', 'password'}


def audit(action, user_id=None, entity_type=None, entity_id=None, status='SUCCESS', details=None, commit=True):
    """Best-effort audit write — never breaks the request that triggered it."""
    try:
        safe = {k: v for k, v in (details or {}).items() if k.lower() not in _FORBIDDEN}
        db.session.add(AuditLogs(
            user_id=user_id, action=action, entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            status=status, details=safe or None,
            ip_address=(request.remote_addr or '')[:64] if request else None,
            user_agent=(request.headers.get('User-Agent') or '')[:255] if request else None,
        ))
        if commit:
            db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.warning(f'[audit] failed to record {action}')
