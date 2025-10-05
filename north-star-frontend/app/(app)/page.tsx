"use client";
import { useAtomValue } from "jotai";
import { roleAtom } from "@/lib/auth";
import { Panel } from "@/components/ui/panel";
import Link from "next/link";

function Stat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-panel p-4 hover:bg-white/[.06]">
      <div className="text-sm text-meta">{label}</div>
      <div className="text-2xl" style={{ fontFamily: "var(--font-lexend)" }}>{value}</div>
    </div>
  );
}

function SkillSignal({ data }: { data: { name: string; value: number }[] }) {
  const palette = ["#3B82F6","#8B5CF6","#14B8A6","#60A5FA","#A78BFA","#34D399"];
  return (
    <div className="space-y-3">
      {data.map((d,i)=> (
        <div key={i} className="group">
          <div className="mb-1 flex items-center justify-between text-xs text-meta">
            <span>{d.name}</span>
            <span className="rounded-md bg-white/5 px-1.5 py-0.5 text-[10px] text-white">{(d.value*100).toFixed(0)}%</span>
          </div>
          <div role="meter" aria-valuemin={0} aria-valuemax={1} aria-valuenow={d.value} className="relative h-3 rounded-full bg-white/5">
            <div className="h-3 rounded-full transition-all" style={{ width: `${Math.max(4, d.value * 100)}%`, background: `linear-gradient(90deg, ${palette[i%palette.length]}, ${palette[(i+1)%palette.length]})`, boxShadow: `0 0 16px ${palette[i%palette.length]}40` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const role = useAtomValue(roleAtom);
  const isDev = role === "Dev";
  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Panel className={`${isDev ? "lg:col-span-2" : "lg:col-span-3"} p-4`}>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-lg font-semibold">StarView</h3>
          <span className="text-sm text-meta">API reachable</span>
        </div>
        <div className={`grid grid-cols-1 gap-3 ${isDev ? "sm:grid-cols-3" : "sm:grid-cols-4"}`}>
          <Stat label="Projects" value={2} />
          <Stat label="Users" value={7} />
          <Stat label="Deploys" value={19} />
          {!isDev && <Stat label="Audit Events" value={42} />}
          {isDev && <Stat label="Skill Samples" value={128} />}
        </div>
      </Panel>

      {isDev && (
        <Panel className="p-4">
          <div className="mb-2 text-lg font-semibold">Skill Signal</div>
          <SkillSignal data={[
            { name: "typescript", value: 0.91 },
            { name: "nextjs", value: 0.83 },
            { name: "tailwind", value: 0.78 },
            { name: "vitest", value: 0.69 }
          ]}/>
        </Panel>
      )}

      <Panel className="lg:col-span-3 p-4">
        <div className="text-lg font-semibold mb-2">Smart Access</div>
        <div className="flex flex-wrap gap-2">
          {["NorthStar Guide","IntelliStaff","IntelliSelf","Aurora","Audit"].map((q)=> (
            <span key={q} className="rounded-2xl border border-white/10 px-4 py-2 hover:bg-white/5">
              <Link href={q==="NorthStar Guide"?"/guide":`/${q.toLowerCase()}`.replace(" ","")}>{q}</Link>
            </span>
          ))}
        </div>
      </Panel>
    </div>
  );
}
