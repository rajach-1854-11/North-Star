import { atom } from "jotai";
import { jwtDecode } from "jwt-decode";

export type Role = "Admin" | "PO" | "BA" | "Dev";

export type Claims = {
  sub?: string;
  username?: string;
  role?: Role;
  tenant_id?: string;
  developer_id?: number;
  exp?: number;
  [k: string]: any;
};

function loadToken() { if (typeof window === "undefined") return null; return localStorage.getItem("ns_token"); }
export const tokenAtom = atom<string | null>(loadToken());
export const claimsAtom = atom<Claims | null>((get) => {
  const t = get(tokenAtom); if (!t) return null;
  try { return jwtDecode<Claims>(t); } catch { return null; }
});
export const roleAtom = atom<Role | null>((get) => get(claimsAtom)?.role ?? null);
export const tenantAtom = atom<string | null>((get) => get(claimsAtom)?.tenant_id ?? null);

export const setTokenAtom = atom(null, (_get, set, token: string | null) => {
  if (typeof window !== "undefined") {
    if (token) localStorage.setItem("ns_token", token);
    else localStorage.removeItem("ns_token");
  }
  set(tokenAtom, token);
});
