"use client";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { api } from "@/lib/api";
import { useSetAtom } from "jotai";
import { setTokenAtom } from "@/lib/auth";
import { toast } from "sonner";

export default function LoginPage() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const setToken = useSetAtom(setTokenAtom);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.login(username, password);
      setToken(res.access_token);
      toast.success("Welcome back!");
      window.location.href = "/";
    } catch (err: any) {
      toast.error(err?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen grid place-items-center relative overflow-hidden">
      <style>{`
        @keyframes shoot { from { transform: translateX(-120%) translateY(0) rotate(20deg); opacity: 0;} 15% {opacity:1;} to { transform: translateX(140%) translateY(0) rotate(20deg); opacity:0;} }
        @keyframes twinkle { 0%,100%{opacity:.5} 50%{opacity:1} }
      `}</style>
      <div className="pointer-events-none absolute left-[-10%] top-16 h-1 w-[60%]" style={{ animation: "shoot 1.6s ease-out 0s 1" }}>
        <div className="h-1 w-full" style={{ background: "linear-gradient(90deg, #FDE68A 0%, rgba(253,230,138,0) 90%)" }} />
        <svg width="22" height="22" viewBox="0 0 24 24" fill="#FACC15" className="absolute -top-2 left-0" style={{ filter: "drop-shadow(0 0 6px #FACC15)" }}>
          <polygon points="12,2 15,9 22,9 16,13 18,21 12,16 6,21 8,13 2,9 9,9" />
        </svg>
      </div>
      <div className="pointer-events-none absolute right-10 top-8 text-yellow-300/80" style={{ animation: "twinkle 2.6s ease-in-out infinite" }}>✦</div>
      <div className="pointer-events-none absolute right-24 top-24 text-yellow-300/60" style={{ animation: "twinkle 3.2s ease-in-out .4s infinite" }}>✧</div>

      <div className="w-full max-w-md">
        <Panel className="p-6">
          <h1 className="text-center text-2xl font-semibold mb-1" style={{ fontFamily: "var(--font-lexend)" }}>Your personal NorthStar 🌠</h1>
          <p className="text-center text-meta mb-6">Sign in to continue</p>
          <form className="space-y-3" onSubmit={onSubmit}>
            <div><label className="text-sm text-meta">Username</label><Input value={username} onChange={e=>setUsername((e.target as HTMLInputElement).value)} required /></div>
            <div><label className="text-sm text-meta">Password</label><Input type="password" value={password} onChange={e=>setPassword((e.target as HTMLInputElement).value)} required /></div>
            <Button disabled={loading} className="w-full">{loading ? "Signing in…" : "Sign in"}</Button>
          </form>
        </Panel>
      </div>
    </main>
  );
}
