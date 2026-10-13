from portal import db
from .base import CrudMixin, utcnow


class LoginEvent:
    OTP_LOGIN = 'OTP_LOGIN'
    STAFF_LOGIN = 'STAFF_LOGIN'        # Admin / Customer Support: email + PIN
    PIN_UNLOCK = 'PIN_UNLOCK'
    BIOMETRIC_UNLOCK = 'BIOMETRIC_UNLOCK'
    LOGOUT = 'LOGOUT'


class LoginStatus:
    SUCCESS = 'SUCCESS'
    FAILED = 'FAILED'
    BLOCKED = 'BLOCKED'


class LoginHistory(CrudMixin, db.Model):
    """Every sign-in / unlock / logout attempt, successful or not."""
    __tablename__ = 'login_history'

    login_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=True, index=True)
    event = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(10), nullable=False)
    failure_reason = db.Column(db.String(60), nullable=True)
    session_id = db.Column(db.Integer, db.ForeignKey('user_sessions.session_id'), nullable=True)
    device_binding_id = db.Column(db.Integer, db.ForeignKey('device_bindings.device_binding_id'), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
