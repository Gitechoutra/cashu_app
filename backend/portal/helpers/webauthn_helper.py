"""Biometric unlock via WebAuthn platform authenticators (fingerprint, Face ID,
Windows Hello). The biometric check happens on the device; the server only
verifies a signature from a key that never leaves it."""

import json
from datetime import timedelta

from flask import current_app
from webauthn import (
    generate_authentication_options, generate_registration_options, options_to_json,
    verify_authentication_response, verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorAttachment, AuthenticatorSelectionCriteria, PublicKeyCredentialDescriptor,
    ResidentKeyRequirement, UserVerificationRequirement,
)

from portal.models.base import utcnow

CHALLENGE_TTL = timedelta(minutes=3)


def _rp():
    c = current_app.config
    return c['WEBAUTHN_RP_ID'], c['WEBAUTHN_RP_NAME'], c['WEBAUTHN_ORIGIN']


def _store_challenge(session, challenge):
    session.webauthn_challenge = bytes_to_base64url(challenge)
    session.webauthn_challenge_expires = utcnow() + CHALLENGE_TTL


def _pop_challenge(session):
    ch, exp = session.webauthn_challenge, session.webauthn_challenge_expires
    session.webauthn_challenge = None
    session.webauthn_challenge_expires = None
    if not ch or not exp or exp < utcnow():
        return None
    return base64url_to_bytes(ch)


def registration_options(user, session, existing_credentials):
    rp_id, rp_name, _ = _rp()
    opts = generate_registration_options(
        rp_id=rp_id, rp_name=rp_name,
        user_id=user.public_id.encode(), user_name=user.mobile_number,
        user_display_name=user.full_name or user.masked_mobile,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM,
            resident_key=ResidentKeyRequirement.DISCOURAGED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
                             for c in existing_credentials],
    )
    _store_challenge(session, opts.challenge)
    return json.loads(options_to_json(opts))


def verify_registration(session, credential):
    rp_id, _, origin = _rp()
    challenge = _pop_challenge(session)
    if challenge is None:
        raise ValueError('Biometric setup timed out. Please try again.')
    v = verify_registration_response(
        credential=credential, expected_challenge=challenge, expected_rp_id=rp_id,
        expected_origin=origin, require_user_verification=True,
    )
    return bytes_to_base64url(v.credential_id), bytes_to_base64url(v.credential_public_key), v.sign_count


def authentication_options(session, credentials):
    rp_id, _, _ = _rp()
    opts = generate_authentication_options(
        rp_id=rp_id,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(c.credential_id))
                           for c in credentials],
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    _store_challenge(session, opts.challenge)
    return json.loads(options_to_json(opts))


def verify_authentication(session, credential, stored):
    rp_id, _, origin = _rp()
    challenge = _pop_challenge(session)
    if challenge is None:
        raise ValueError('Biometric check timed out. Please try again.')
    v = verify_authentication_response(
        credential=credential, expected_challenge=challenge, expected_rp_id=rp_id,
        expected_origin=origin, credential_public_key=base64url_to_bytes(stored.public_key),
        credential_current_sign_count=stored.sign_count, require_user_verification=True,
    )
    return v.new_sign_count
