import { describe, it, expect } from "vitest";
import { canView } from "@/lib/rbac";
describe("RBAC view guards", () => {
  it("admin can see all", () => {
    expect(canView("/intellistaff","Admin" as any)).toBe(true);
    expect(canView("/intelliself","Admin" as any)).toBe(true);
  });
  it("dev cannot see intellistaff", () => {
    expect(canView("/intellistaff","Dev" as any)).toBe(false);
  });
  it("po can see audit", () => {
    expect(canView("/audit","PO" as any)).toBe(true);
  });
});
