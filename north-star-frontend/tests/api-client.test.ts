import { describe, it, expect } from "vitest";
import { TokenResp } from "@/lib/api";
describe("zod schemas", () => {
  it("parses token", () => {
    const parsed = TokenResp.safeParse({ access_token: "x.y.z", token_type: "bearer" });
    expect(parsed.success).toBe(true);
  });
  it("rejects invalid token", () => {
    const parsed = TokenResp.safeParse({});
    expect(parsed.success).toBe(false);
  });
});
