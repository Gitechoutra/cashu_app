"""
Keeps staff accounts in the database in sync with the seed files.

Each account in seed_admin.py / seed_customersupport.py has a fixed `key`.
On every backend start (and on every save of those files while the dev server
runs — Flask's reloader restarts the app), sync_staff():

  * creates the account if it doesn't exist (or adopts an existing account with
    that mobile number),
  * applies the mobile number, name, role and PIN from the file,
  * signs the account out everywhere when its mobile number, PIN or role changes,
  * suspends accounts whose entry was removed from the file.

PINs are stored only as salted hashes and are never logged.
"""

import logging

from werkzeug.security import check_password_hash, generate_password_hash

from portal import db
from portal.helpers.validators import normalize_mobile, validate_email, validate_name, validate_staff_pin
from portal.models.base import utcnow
from portal.models.roles import Roles, RoleName
from portal.models.user_sessions import UserSessions, SessionStatus
from portal.models.users import Users, UserStatus

logger = logging.getLogger('cardvault.seeders')


def _revoke_all(user, reason):
    for s in UserSessions.query.filter_by(user_id=user.user_id, status=SessionStatus.ACTIVE):
        s.status = SessionStatus.REVOKED
        s.revoked_reason = reason


def _audit(action, user, details):
    from portal.models.audit_logs import AuditLogs
    db.session.add(AuditLogs(user_id=user.user_id, action=action, entity_type='USER', entity_id=user.public_id,
                             status='SUCCESS', details=details))


def sync_staff(accounts, role_name, file_label):
    """accounts: list of dicts {key, mobile_number, full_name, pin}. Returns a summary string."""
    role_id = Roles.id_for(role_name)
    seen, created, updated, problems = set(), 0, 0, []

    for i, acc in enumerate(accounts, 1):
        key = str(acc.get('key') or '').strip()[:40]
        if not key:
            problems.append(f'entry {i}: missing key')
            continue
        if key in seen:
            problems.append(f'{key}: duplicate key')
            continue
        seen.add(key)

        mobile, err = normalize_mobile(acc.get('mobile_number'))
        if err:
            problems.append(f'{key}: invalid mobile_number')
            continue
        name, err = validate_name(acc.get('full_name'), required=True)
        if err:
            problems.append(f'{key}: invalid full_name')
            continue
        email, err = validate_email(acc.get('email'), required=True)
        if err:
            problems.append(f'{key}: invalid email')
            continue
        # Staff sign in with email + PIN only (no OTP), so a PIN is mandatory.
        pin, err = validate_staff_pin(acc.get('pin'))
        if err:
            problems.append(f'{key}: missing, weak or invalid PIN ({err}) — set it in .env or the seed file')
            continue

        user = Users.query.filter_by(seed_key=key).first()
        owner = Users.query.filter_by(mobile_number=mobile).first()
        if user is None:
            if owner is not None and owner.seed_key and owner.seed_key != key:
                problems.append(f'{key}: mobile already used by seeded account "{owner.seed_key}"')
                continue
            if owner is not None and owner.role_name not in (RoleName.ADMIN, RoleName.SUPPORT):
                problems.append(f'{key}: mobile number belongs to a customer account — staff need their own number')
                continue
            user = owner            # adopt an existing staff account with that number, if any
        elif owner is not None and owner.user_id != user.user_id:
            problems.append(f'{key}: mobile number belongs to another account — not changed')
            continue
        email_owner = Users.query.filter_by(email=email).first()
        if email_owner is not None and (user is None or email_owner.user_id != user.user_id):
            problems.append(f'{key}: email already used by another account')
            continue

        if user is None:
            user = Users(mobile_number=mobile, email=email, full_name=name, role_id=role_id, status=UserStatus.ACTIVE, seed_key=key)
            if pin:
                user.pin_hash, user.pin_set_at = generate_password_hash(pin), utcnow()
            db.session.add(user)
            db.session.flush()
            _audit('STAFF_SEED_CREATED', user, {'key': key, 'role': role_name, 'source': file_label})
            created += 1
            continue

        changes = []
        if user.seed_key != key:
            user.seed_key = key
            changes.append('adopted')
        if user.mobile_number != mobile:
            user.mobile_number = mobile
            changes.append('mobile_number')
        if user.email != email:
            user.email = email
            changes.append('email')
        if user.full_name != name:
            user.full_name = name
            changes.append('full_name')
        if user.role_id != role_id:
            user.role_id = role_id
            changes.append('role')
        if user.status != UserStatus.ACTIVE:
            user.status = UserStatus.ACTIVE
            changes.append('status')
        if pin and not (user.pin_hash and check_password_hash(user.pin_hash, pin)):
            user.pin_hash, user.pin_set_at, user.pin_failed_attempts = generate_password_hash(pin), utcnow(), 0
            user.pin_locked_until, user.pin_reset_required = None, False
            changes.append('pin')
        if changes:
            if {'mobile_number', 'email', 'pin', 'role', 'adopted'} & set(changes):
                _revoke_all(user, 'SEED_CREDENTIALS_CHANGED')
            _audit('STAFF_SEED_UPDATED', user, {'key': key, 'changed': changes, 'source': file_label})
            updated += 1

    # Entries removed from the file: suspend (never delete — keeps audit history and tickets intact).
    removed = 0
    for u in Users.query.filter(Users.seed_key.isnot(None), Users.role_id == role_id).all():
        if u.seed_key not in seen and u.status != UserStatus.SUSPENDED:
            u.status = UserStatus.SUSPENDED
            _revoke_all(u, 'SEED_ENTRY_REMOVED')
            _audit('STAFF_SEED_REMOVED', u, {'key': u.seed_key, 'source': file_label})
            removed += 1

    db.session.commit()
    for p in problems:
        logger.error(f'[seed] {file_label}: {p}')
    return f'{created} created, {updated} updated, {removed} suspended' + (f', {len(problems)} skipped' if problems else '')


def managed_fields(user):
    """Which of this user's fields the seed files control (empty set = not seed-managed).
    Used to refuse in-app edits that the next seeder run would silently undo."""
    if not getattr(user, 'seed_key', None):
        return set()
    return {'mobile_number', 'email', 'full_name', 'role', 'status', 'pin'}
