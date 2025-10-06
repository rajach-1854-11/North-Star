"use client";
import { Panel } from "@/components/ui/panel";

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

export default function IntelliSelf() {
  return (
    <Panel className="p-4">
      <div className="text-xl font-semibold mb-3">IntelliSelf — Your Skills</div>
      <SkillSignal data={[{ name: "typescript", value: 0.91 },{ name: "nextjs", value: 0.83 },{ name: "tailwind", value: 0.78 },{ name: "vitest", value: 0.69 }]}/>
      <table className="w-full text-sm mt-4">
        <thead className="bg-white/5"><tr><th className="px-3 py-2 text-left">Path</th><th className="px-3 py-2 text-left">Score</th><th className="px-3 py-2 text-left">Last Seen</th></tr></thead>
        <tbody>
          {[{ path: "typescript", score: 0.91, last: "2025-10-02" },{ path: "nextjs", score: 0.83, last: "2025-10-01" },{ path: "tailwind", score: 0.78, last: "2025-09-28" }].map((s,i)=> (
            <tr key={i} className="border-t border-white/10"><td className="px-3 py-2">{s.path}</td><td className="px-3 py-2">{s.score.toFixed(2)}</td><td className="px-3 py-2">{s.last}</td></tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
