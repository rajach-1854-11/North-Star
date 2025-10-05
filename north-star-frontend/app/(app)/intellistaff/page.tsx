"use client";
import { useState, useMemo } from "react";
import { Panel } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

type Candidate = { id: number; fit: number; skills: string[] };

export default function IntelliStaff() {
  const [project, setProject] = useState("PX");
  const [skill, setSkill] = useState("");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<number[]>([]);

  const candidates: Candidate[] = [
    { id: 23, fit: 0.88, skills: ["react","fastapi","qdrant"] },
    { id: 42, fit: 0.79, skills: ["python","nextjs","qdrant"] },
    { id: 17, fit: 0.74, skills: ["react","typescript"] },
    { id: 58, fit: 0.70, skills: ["python","fastapi"] }
  ];

  const filtered = useMemo(()=> candidates
      .filter(c => !skill || c.skills.includes(skill))
      .filter(c => !query || `${c.id}`.includes(query.trim()))
      .sort((a,b)=> b.fit-a.fit), [candidates, skill, query]);

  const allVisibleIds = filtered.map(c=>c.id);
  const allSelectedVisible = allVisibleIds.every(id => selected.includes(id)) && allVisibleIds.length>0;
  const toggleOne = (id: number) => setSelected(prev=> prev.includes(id) ? prev.filter(x=>x!==id) : [...prev,id]);
  const toggleAllVisible = () => setSelected(prev=> allSelectedVisible ? prev.filter(x=>!allVisibleIds.includes(x)) : Array.from(new Set([...prev, ...allVisibleIds])));

  function assign(withJira: boolean) {
    alert(`${selected.length} developer(s) assigned to ${project}` + (withJira ? " and Jira epic(s) requested." : "."));
    setSelected([]);
  }

  return (
    <div className="space-y-4">
      <Panel className="p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <div><div className="text-xs text-meta mb-1">Project</div>
            <Select value={project} onChange={e=>setProject((e.target as HTMLSelectElement).value)}>
              <option value="PX">PX — Realtime Pricing</option>
              <option value="NS">NS — North Star</option>
            </Select>
          </div>
          <div><div className="text-xs text-meta mb-1">Filter by Skill</div>
            <Select value={skill} onChange={e=>setSkill((e.target as HTMLSelectElement).value)}>
              <option value="">All skills</option>
              <option value="react">react</option>
              <option value="fastapi">fastapi</option>
              <option value="qdrant">qdrant</option>
              <option value="python">python</option>
              <option value="nextjs">nextjs</option>
              <option value="typescript">typescript</option>
            </Select>
          </div>
          <div className="md:col-span-2"><div className="text-xs text-meta mb-1">Search developer (by id)</div>
            <Input placeholder="e.g., 23" value={query} onChange={e=>setQuery((e.target as HTMLInputElement).value)} />
          </div>
        </div>
      </Panel>

      <Panel className="p-0 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-3">
            <input aria-label="Select all visible" type="checkbox" checked={allSelectedVisible} onChange={toggleAllVisible} />
            <div className="text-sm text-meta">{selected.length} selected</div>
          </div>
          <div className="text-sm text-meta">{filtered.length} candidates</div>
        </div>
        <div className="divide-y divide-white/10">
          {filtered.map((c)=> (
            <div key={c.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <input aria-label={`Select developer ${c.id}`} type="checkbox" checked={selected.includes(c.id)} onChange={()=>toggleOne(c.id)} />
                  <div>
                    <div className="text-xl font-semibold">Developer #{c.id}</div>
                    <div className="text-sm text-meta">Fit: {(c.fit * 100).toFixed(1)}% · Skills: {c.skills.join(", ")}</div>
                  </div>
                </div>
                <div className="text-sm text-meta">ID: {c.id}</div>
              </div>
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-2 border-t border-white/10 bg-[#0F1520] p-4 md:flex-row md:items-center md:justify-between">
          <div className="text-xs text-meta">After assigning, a plan will be generated automatically for each developer.</div>
          <div className="flex gap-2">
            <Button variant="outline" disabled={selected.length === 0} onClick={()=>assign(false)}>Assign to {project}</Button>
            <Button disabled={selected.length === 0} onClick={()=>assign(true)}>Assign + Create Jira Epic</Button>
          </div>
        </div>
      </Panel>
    </div>
  );
}
