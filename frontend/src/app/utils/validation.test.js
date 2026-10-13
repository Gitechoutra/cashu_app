import { describe, expect, it } from "vitest";
import {
  previewFigures, validateAmount, validateCardForm, validateDate, validateLast4, validateMobile,
  validatePayment, validatePin,
} from "./validation";
import { daysUntil, fmtINR } from "./format";

const base = {
  card_nickname: "Regalia", last_four_digits: "4242", credit_limit: "200000",
  outstanding_balance: "45000.50", available_credit: "", minimum_amount_due: "2250", billing_day: "12", due_date: "",
};

describe("validation mirrors the backend", () => {
  it("mobile", () => {
    expect(validateMobile("9876543210")).toBe("");
    expect(validateMobile("+91 98765 43210")).toBe("");
    expect(validateMobile("5876543210")).not.toBe("");
  });
  it("last four digits", () => {
    expect(validateLast4("0042")).toBe("");
    ["424", "42424", "42a4", ""].forEach((v) => expect(validateLast4(v)).not.toBe(""));
  });
  it("pin rejects weak values", () => {
    expect(validatePin("4826")).toBe("");
    ["1111", "1234", "9876", "12"].forEach((v) => expect(validatePin(v)).not.toBe(""));
  });
  it("amounts: precision, sign, notation", () => {
    expect(validateAmount("1,50,000.50", "x")).toBe("");
    ["-5", "1e5", "10.555", "abc"].forEach((v) => expect(validateAmount(v, "x")).not.toBe(""));
    expect(validateAmount("0", "x", { allowZero: false })).not.toBe("");
    expect(validateAmount("", "x", { required: true })).not.toBe("");
  });
  it("dates range", () => {
    const today = new Date(2026, 9, 9);
    expect(validateDate("2026-10-20", "d", { today })).toBe("");
    expect(validateDate("2020-01-01", "d", { today })).not.toBe("");
    expect(validateDate("20-10-2026", "d", { today })).not.toBe("");
  });
  it("card form cross-field rules", () => {
    expect(validateCardForm(base)).toEqual({});
    expect(validateCardForm({ ...base, minimum_amount_due: "50000" }).minimum_amount_due).toBeTruthy();
    expect(validateCardForm({ ...base, available_credit: "300000" }).available_credit).toBeTruthy();
    expect(validateCardForm({ ...base, credit_limit: "0" }).credit_limit).toBeTruthy();
    expect(validateCardForm({ ...base, billing_day: "32" }).billing_day).toBeTruthy();
    expect(validateCardForm(base, { requireIssuerName: true }).issuer_name).toBeTruthy();
  });
  it("preview: utilisation, reported vs estimated, zero limit", () => {
    const p = previewFigures(base);
    expect(p.utilization).toBeCloseTo(22.50025, 5);
    expect(p.availableBasis).toBe("ESTIMATED");
    expect(previewFigures({ ...base, available_credit: "150000" }).availableBasis).toBe("REPORTED");
    expect(previewFigures({ ...base, credit_limit: "0" }).utilization).toBeNull();
  });
  it("payment amount", () => {
    expect(validatePayment("5000", "45000.50")).toBe("");
    expect(validatePayment("45000.51", "45000.50")).not.toBe("");
    expect(validatePayment("0.5", null)).not.toBe("");
  });
});

describe("format", () => {
  it("formats INR and handles missing values", () => {
    expect(fmtINR("45000.5")).toBe("₹45,000.50");
    expect(fmtINR(null)).toBe("—");
  });
  it("daysUntil", () => {
    expect(daysUntil("2026-10-19", new Date(2026, 9, 9))).toBe(10);
  });
});
