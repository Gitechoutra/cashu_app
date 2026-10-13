/** Where each role lands after sign-in / unlock. The server enforces access;
 *  this only picks which screens to show. */
export const HOME_BY_ROLE = { ADMIN: "/admin", SUPPORT: "/support", USER: "/user" };

export const homeFor = (role) => HOME_BY_ROLE[role] || "/user";

export const ROLE_LABEL = { ADMIN: "Admin", SUPPORT: "Customer Support", USER: "User" };

/** Sign-in page for each role: customers use mobile + OTP, staff use email + PIN. */
export const LOGIN_BY_ROLE = { ADMIN: "/admin/login", SUPPORT: "/support/login", USER: "/signin" };
export const loginFor = (role) => LOGIN_BY_ROLE[role] || "/signin";
export const isStaff = (role) => role === "ADMIN" || role === "SUPPORT";
/** Staff PINs are 6 digits (they sign in without OTP); customer PINs are 4. */
export const pinLengthFor = (role) => (isStaff(role) ? 6 : 4);
