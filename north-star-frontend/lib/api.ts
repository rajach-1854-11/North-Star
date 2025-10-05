import ky, { HTTPError } from "ky";
import { z } from "zod";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE;

if (!API_BASE) {
  throw new Error("NEXT_PUBLIC_API_BASE is not defined. Set it in your environment (e.g. .env.local).");
}

const INTELLISTAFF_PATH = process.env.NEXT_PUBLIC_INTELLISTAFF_PATH ?? "/intellistaff/candidates";

export const Candidate = z.object({
  id: z.number(),
  name: z.string(),
  fit: z.number(),
  skills: z.array(z.string())
});

const CandidateArray = z.array(Candidate);
const CandidateEnvelope = z.object({
  candidates: z.array(Candidate)
});

export type CandidateType = z.infer<typeof Candidate>;

function parseCandidates(payload: unknown): CandidateType[] {
  const direct = CandidateArray.safeParse(payload);
  if (direct.success) {
    return direct.data;
  }
  const enveloped = CandidateEnvelope.safeParse(payload);
  if (enveloped.success) {
    return enveloped.data.candidates;
  }
  throw new Error("Unexpected candidate payload from API");
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
  async listCandidates(params: { project?: string; skill?: string; search?: string } = {}) {
    const searchParams = new URLSearchParams();
    if (params.project) searchParams.set("project", params.project);
    if (params.skill) searchParams.set("skill", params.skill);
    if (params.search) searchParams.set("search", params.search);

    try {
      const response = await ky.get(new URL(INTELLISTAFF_PATH, API_BASE), {
        searchParams,
        timeout: 10000
      }).json();
      return parseCandidates(response);
    } catch (err) {
      if (err instanceof HTTPError) {
        const data = await err.response.json().catch(() => null);
        const detail = data?.detail || data?.message || err.response.statusText;
        throw new Error(typeof detail === "string" ? detail : "Unable to load candidates");
      }
      throw err;
    }
  },
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
