/** WebAuthn helpers: convert the server's JSON options (base64url) to the
 *  ArrayBuffers the browser API needs, and serialise the result back. */

const b64urlToBuf = (s) => {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const bin = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(bin, (c) => c.charCodeAt(0)).buffer;
};

const bufToB64url = (buf) =>
  btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

export async function isBiometricAvailable() {
  try {
    return !!(window.PublicKeyCredential &&
      (await window.PublicKeyCredential.isUserVerifyingPlatformAuthenticatorAvailable()));
  } catch {
    return false;
  }
}

export async function createCredential(options) {
  const publicKey = {
    ...options,
    challenge: b64urlToBuf(options.challenge),
    user: { ...options.user, id: b64urlToBuf(options.user.id) },
    excludeCredentials: (options.excludeCredentials || []).map((c) => ({ ...c, id: b64urlToBuf(c.id) })),
  };
  const cred = await navigator.credentials.create({ publicKey });
  return {
    id: cred.id,
    rawId: bufToB64url(cred.rawId),
    type: cred.type,
    response: {
      clientDataJSON: bufToB64url(cred.response.clientDataJSON),
      attestationObject: bufToB64url(cred.response.attestationObject),
      transports: cred.response.getTransports ? cred.response.getTransports() : [],
    },
    clientExtensionResults: cred.getClientExtensionResults ? cred.getClientExtensionResults() : {},
    authenticatorAttachment: cred.authenticatorAttachment || undefined,
  };
}

export async function getAssertion(options) {
  const publicKey = {
    ...options,
    challenge: b64urlToBuf(options.challenge),
    allowCredentials: (options.allowCredentials || []).map((c) => ({ ...c, id: b64urlToBuf(c.id) })),
  };
  const a = await navigator.credentials.get({ publicKey });
  return {
    id: a.id,
    rawId: bufToB64url(a.rawId),
    type: a.type,
    response: {
      clientDataJSON: bufToB64url(a.response.clientDataJSON),
      authenticatorData: bufToB64url(a.response.authenticatorData),
      signature: bufToB64url(a.response.signature),
      userHandle: a.response.userHandle ? bufToB64url(a.response.userHandle) : null,
    },
    clientExtensionResults: a.getClientExtensionResults ? a.getClientExtensionResults() : {},
    authenticatorAttachment: a.authenticatorAttachment || undefined,
  };
}
