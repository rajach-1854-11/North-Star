import * as React from "react";
import { clsx } from "clsx";
export function Panel({ className, children }: React.PropsWithChildren<{ className?: string }>) {
  return (
    <div className={clsx("relative rounded-2xl border border-white/10 bg-panel shadow-soft transition-all duration-300 hover:-translate-y-0.5 hover:shadow-lift", className)} style={{ backgroundImage: "radial-gradient(60% 50% at 30% 0%, rgba(59,130,246,0.08) 0%, rgba(0,0,0,0) 60%), radial-gradient(40% 40% at 100% 0%, rgba(139,92,246,0.06) 0%, rgba(0,0,0,0) 70%)" }}>
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/15 to-transparent" />
      <div className="relative">{children}</div>
    </div>
  );
}
