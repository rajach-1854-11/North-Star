"use client";
import { useAtomValue, useSetAtom } from "jotai";
import { claimsAtom, roleAtom, setTokenAtom } from "@/lib/auth";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const role = useAtomValue(roleAtom);
  const claims = useAtomValue(claimsAtom);
  const pathname = usePathname();
  const router = useRouter();
  const setToken = useSetAtom(setTokenAtom);

  if (!claims) {
    if (typeof window !== "undefined") router.replace("/login");
    return null;
  }

  const items = [
    { href: "/", label: "Dashboard" },
    { href: "/guide", label: "NorthStar Guide" },
    { href: "/intellistaff", label: "IntelliStaff", roles: ["PO","BA"] },
    { href: "/intelliself", label: "IntelliSelf", roles: ["Dev"] },
    { href: "/audit", label: "Audit", roles: ["PO", "Admin"] },
    { href: "/aurora", label: "Aurora" },
    { href: "/admin/users", label: "Admin · Users", roles: ["Admin"] }
  ];

  function logout() { setToken(null); window.location.href = "/login"; }

  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <aside className="border-r border-white/10 bg-panel px-4 py-6">
        <nav className="space-y-1">
          {items.filter(i => role === "Admin" || !i.roles || i.roles.includes(role!)).map(i => {
            const active = pathname === i.href;
            return (
              <Link key={i.href} href={i.href} className="group block rounded-2xl px-2 py-1 hover:bg-white/5">
                <div className="grid grid-cols-[6px_1fr] items-center gap-3">
                  <span className={`h-8 rounded-full transition-colors ${active ? "bg-gradient-to-b from-action via-subtlePurple to-mutedTeal" : "bg-transparent"}`} />
                  <span className={`text-sm ${active ? "text-white" : "text-text"}`}>{i.label}</span>
                </div>
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="flex min-h-screen flex-col">
        <header className="sticky top-0 z-10 border-b border-white/10 bg-deep/80 backdrop-blur">
          <div className="mx-auto grid max-w-[1400px] grid-cols-[1fr_auto] items-center gap-3 px-6 py-3">
            <div className="flex items-center gap-3">
              <span className="text-lg font-semibold bg-clip-text text-transparent" style={{ backgroundImage: "linear-gradient(90deg,#E5E7EB,#A5B4FC)", fontFamily: "var(--font-lexend)" }}>✦ North Star</span>
              <span className="inline-flex items-center gap-2 rounded-2xl border border-white/10 px-2 py-0.5 text-xs text-meta">
                <span className="inline-block h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_0_2px_rgba(20,184,166,0.25)]" aria-label="API healthy" /> API: Healthy
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-2xl border border-white/10 px-2 py-0.5 text-xs text-meta">{claims?.username}</span>
              <span className="rounded-2xl border border-white/10 px-2 py-0.5 text-xs text-meta">{claims?.role}</span>
              <span className="rounded-2xl border border-white/10 px-2 py-0.5 text-xs text-meta">{claims?.tenant_id}</span>
              <Button variant="outline" onClick={logout}>Logout</Button>
            </div>
          </div>
        </header>
        <main className="px-6 pb-10 pt-4">{children}</main>
      </div>
    </div>
  );
}
