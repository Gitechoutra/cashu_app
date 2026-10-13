import { describe, expect, it } from "vitest";
import { buildUpiLink, classifyQr } from "./upi";

describe("UPI QR parsing", () => {
  it("parses a merchant UPI code", () => {
    const r = classifyQr("upi://pay?pa=merchant.shop@okaxis&pn=Sri%20Ganesh%20Stores&mc=5411&tn=Order%2042&am=250.50&cu=INR");
    expect(r.kind).toBe("upi");
    expect(r.payee).toMatchObject({ vpa: "merchant.shop@okaxis", name: "Sri Ganesh Stores", amount: "250.50", merchantCode: "5411" });
  });
  it("accepts codes without amount and appends one when paying", () => {
    const r = classifyQr("upi://pay?pa=asha@ybl&pn=Asha");
    expect(r.payee.amount).toBeNull();
    expect(buildUpiLink(r, "99.5")).toBe("upi://pay?pa=asha@ybl&pn=Asha&am=99.50&cu=INR");
  });
  it("passes signed merchant codes through unchanged", () => {
    const raw = "upi://pay?pa=mstore@icici&pn=M&am=10.00&cu=INR&sign=ABC123";
    expect(buildUpiLink(classifyQr(raw), "50")).toBe(raw);
  });
  it("rejects bad UPI codes", () => {
    expect(classifyQr("upi://pay?pa=not-a-vpa").kind).toBe("invalid-upi");
    expect(classifyQr("upi://pay?pa=asha@okhdfc&am=-5").kind).toBe("invalid-upi");
    expect(classifyQr("upi://pay?pa=asha@okhdfc&am=1e5").kind).toBe("invalid-upi");
    expect(classifyQr("upi://pay?pa=asha@okhdfc&cu=USD").kind).toBe("invalid-upi");
    expect(classifyQr("upi://mandate?pa=asha@okhdfc").kind).toBe("invalid-upi");
  });
  it("strips markup from payee names", () => {
    expect(classifyQr("upi://pay?pa=asha@okhdfc&pn=%3Cscript%3EBad").payee.name).toBe("scriptBad");
  });
  it("classifies links and text without opening anything", () => {
    expect(classifyQr("https://example.com/x")).toEqual({ kind: "url", url: "https://example.com/x", host: "example.com" });
    expect(classifyQr("hello").kind).toBe("text");
    expect(classifyQr("javascript:alert(1)").kind).toBe("text");
  });
  it("refuses invalid amounts when building a link", () => {
    expect(buildUpiLink(classifyQr("upi://pay?pa=asha@okhdfc"), "abc")).toBeNull();
  });
});
