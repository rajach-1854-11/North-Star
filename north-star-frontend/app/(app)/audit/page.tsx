"use client";
import { useMemo, useState } from "react";
import { Panel } from "@/components/ui/panel";
import { Select } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export default function AuditPage() {
  const users = [{ id: 1, name: "alice" }, { id: 2, name: "bob" }, { id: 3, name: "carol" }];
  const [actor, setActor] = useState<string>("all");
  const [start, setStart] = useState<string>("");
  const [end, setEnd] = useState<string>("");

  const logs = useMemo(()=> [
    { actor: 1, a: "guide", s: 200, ts: "2025-10-04T19:12:00Z", rid: "req-1" },
    { actor: 2, a: "intellistaff.assign", s: 200, ts: "2025-10-04T19:13:22Z", rid: "req-2" },
    { actor: 1, a: "aurora.plan", s: 200, ts: "2025-10-03T10:05:12Z", rid: "req-3" },
    { actor: 3, a: "admin.patch_role", s: 200, ts: "2025-10-02T09:00:00Z", rid: "req-4" },
  ], []);

  const filtered = logs.filter((x)=> {
    if (actor !== "all" && x.actor !== Number(actor)) return false;
    if (start && new Date(x.ts) < new Date(start)) return false;
    if (end) {
      const endDate = new Date(end); endDate.setDate(endDate.getDate()+1);
      if (new Date(x.ts) >= endDate) return false;
    }
    return true;
  });

  return (
    <Panel className="p-4">
      <div className="text-lg font-semibold mb-2">Audit</div>
      <div className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-4">
        <div><div className="text-xs text-meta mb-1">User</div>
          <Select value={actor} onChange={e=>setActor((e.target as HTMLSelectElement).value)}>
            <option value="all">All users</option>
            {users.map(u=> <option key={u.id} value={u.id}>{u.name}</option>)}
          </Select>
        </div>
        <div><div className="text-xs text-meta mb-1">Start date</div>
          <Input type="date" value={start} onChange={e=>setStart((e.target as HTMLInputElement).value)} />
        </div>
        <div><div className="text-xs text-meta mb-1">End date</div>
          <Input type="date" value={end} onChange={e=>setEnd((e.target as HTMLInputElement).value)} />
        </div>
        <div className="flex items-end"><Button variant="outline" onClick={()=>{ setActor("all"); setStart(""); setEnd(""); }}>Reset</Button></div>
      </div>
      <ul className="space-y-2">
        {filtered.map((x,i)=> (
          <li key={i} className="flex items-center justify-between">
            <div><div className="font-medium">{x.a}</div><div className="text-xs text-meta">{x.ts} — req {x.rid}</div></div>
            <div className="text-sm">{x.s}</div>
          </li>
        ))}
        {filtered.length===0 && (<li className="text-sm text-meta">No audit entries in this range.</li>)}
      </ul>
    </Panel>
  );
}
