"use client";
import { useState } from "react";
import { Panel } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";

export default function GuidePage() {
  const [project, setProject] = useState("");
  const [showNarrative, setShowNarrative] = useState(false);
  const [expandedAB, setExpandedAB] = useState(true);

  function onGuide() { setShowNarrative(true); }

  return (
    <>
      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Panel className="p-4 min-h-[520px] lg:row-span-2">
          <div className="mb-3 flex items-end justify-between gap-3">
            <div><div className="text-xl font-semibold">NorthStar Guide</div><div className="text-sm text-meta">Search knowledge across your tenant</div></div>
            <div className="min-w-[220px]"><Select value={project} onChange={e=>setProject((e.target as HTMLSelectElement).value)}>
              <option value="">All projects</option>
              <option value="PX">PX — Realtime Pricing</option>
              <option value="NS">NS — North Star</option>
            </Select></div>
          </div>
          <Textarea placeholder="Ask a precise question…" rows={10} />
          <div className="mt-2 flex gap-2"><Button onClick={onGuide}>Guide me</Button><Button variant="outline">Copy question</Button></div>
        </Panel>

        <Panel className="overflow-hidden">
          <button className="flex w-full items-center justify-between px-4 py-3 text-left" onClick={()=>setExpandedAB(x=>!x)} aria-expanded={expandedAB}>
            <div className="text-lg font-semibold">A vs B</div><span className="text-meta">{expandedAB ? "▾" : "▸"}</span>
          </button>
          {expandedAB && (
            <div className="grid grid-cols-1 gap-0 md:grid-cols-2">
              {["A","B"].map((col)=> (
                <div key={col} className="p-4 text-base md:text-lg border-t md:border-t-0 md:border-l border-white/10 first:md:border-l-0">
                  <div className="text-meta mb-2">System {col}</div>
                  {["Epic Name","Owner","Status"].map((k)=>(
                    <div key={k} className="mb-2">
                      <div className="text-sm text-meta">{k}</div>
                      <div className="text-base">Value {col}</div>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel className="p-4">
          <div className="mb-2 text-lg font-semibold">Top Evidence</div>
          <div className="space-y-2">
            {[1,2,3].map((i)=> (
              <div key={i} className="rounded-2xl border border-white/10 p-3">
                <div className="flex items-center justify-between text-sm text-meta"><span>{project || "All"} · doc{i}.pdf</span><span>{(0.91 - i * 0.07).toFixed(3)}</span></div>
                <div className="mt-2 text-sm">Relevant passage with highlights …</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {showNarrative && (
        <Modal title="NorthStar Guide — Narrative" onClose={()=>setShowNarrative(false)}>
          <pre className="whitespace-pre-wrap text-sm" style={{ fontFamily: "var(--font-jet)" }}>
Proposed alignment across {project or "selected projects"}:
- Consolidate features under a shared Epic.
- Link subtasks to preserve ownership per stream.
- Flag blockers discovered in A vs B.
          </pre>
          <div className="mt-3 flex gap-2"><Button variant="outline">Copy narrative</Button><Button>Publish to Confluence</Button></div>
        </Modal>
      )}
    </>
  );
}
