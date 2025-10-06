import ky, { HTTPError } from "ky";
import { z } from "zod";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

if (!API_BASE) {
  throw new Error("NEXT_PUBLIC_API_BASE is not defined. Set it in your environment (e.g. .env.local).");
}

export const TokenResp = z.object({
  access_token: z.string(),
  token_type: z.literal("bearer").optional(),
  expires_in: z.number().optional()
});

export const RetrieveHit = z.object({
  text: z.string(),
  score: z.number(),
  source: z.string(),
  chunk_id: z.string()
});
export const RetrieveResp = z.object({
  results: z.array(RetrieveHit),
  message: z.string().nullable().optional(),
  rosetta: z.any().nullable().optional(),
  rosetta_narrative_md: z.string().nullable().optional()
});

export const ProjectsResp = z.array(z.object({
  id: z.number(),
  key: z.string(),
  name: z.string(),
  description: z.string().nullable().optional()
}));

export const api = {
  async login(username: string, password: string) {
    const form = new URLSearchParams();
    form.set("grant_type", "password");
    form.set("scope", "");
    form.set("username", username);
    form.set("password", password);

    try {
      const res = await ky.post(`${API_BASE}/auth/token`, {
        headers: {
          "Content-Type": "application/x-www-form-urlencoded"
        },
        body: form,
        timeout: 10000
      }).json();
      return TokenResp.parse(res);
    } catch (err) {
      if (err instanceof HTTPError) {
        const data = await err.response.json().catch(() => null);
        if (data?.detail) {
          const detail = Array.isArray(data.detail)
            ? data.detail.map((d: any) => d?.msg ?? JSON.stringify(d)).join(", ")
            : String(data.detail);
          throw new Error(detail);
        }
      }
      throw err;
    }
  }
};
