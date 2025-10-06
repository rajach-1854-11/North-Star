"use client";
import { useState } from "react";
import { Panel } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function AuroraPage() {
  const [query, setQuery] = useState("");
  const [showConfirm, setShowConfirm] = useState<null | { type: "jira" | "confluence" }>(null);
  const [devName, setDevName] = useState("dev23");
  const [projectName, setProjectName] = useState("");
  const [projectKey, setProjectKey] = useState("");

  function run() { if (/plan|assign|ticket/i.test(query)) setShowConfirm({ type: "jira" }); else setShowConfirm({ type: "confluence" }); }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Panel className="p-4 lg:col-span-2">
        <div className="text-xl font-semibold mb-1">Aurora</div>
        <div className="text-sm text-meta mb-3">Your personal North Star—explore your projects, draft plans, assign tickets, or refine existing work.</div>
        <Textarea rows={6} placeholder="Ask a question or request a plan (e.g., 'Create an integration plan for PX with dev23')" value={query} onChange={e=>setQuery((e.target as HTMLTextAreaElement).value)} />
        <div className="mt-2 flex gap-2"><Button onClick={run}>Go</Button><Button variant="outline" onClick={()=>setQuery("")}>Clear</Button></div>
      </Panel>

      <Panel className="p-4">
        <div className="text-lg font-semibold mb-2">Create Project (Admin/PO)</div>
        <div className="space-y-2">
          <Input placeholder="Project Name" value={projectName} onChange={e=>setProjectName((e.target as HTMLInputElement).value)} />
          <Input placeholder="Project Key (unique)" value={projectKey} onChange={e=>setProjectKey((e.target as HTMLInputElement).value)} />
          <Button disabled={!projectName || !projectKey}>Create</Button>
        </div>
      </Panel>

      <Panel className="p-4">
        <div className="text-lg font-semibold mb-2">Upload Documents (Admin/PO/BA)</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div><div className="text-xs text-meta mb-1">Project</div>
            <Select defaultValue="PX"><option>PX — Realtime Pricing</option><option>NS — North Star</option></Select>
          </div>
          <div><div className="text-xs text-meta mb-1">File</div>
            <div className="rounded-2xl border border-white/10 px-3 py-2 text-sm text-meta">(file chooser)</div>
          </div>
          <div className="flex items-end"><Button>Upload</Button></div>
        </div>
      </Panel>

      {showConfirm && (
        <Panel className="p-4 lg:col-span-2">
          {showConfirm.type === "jira" ? (
            <div className="flex items-center justify-between">
              <div>
                <div className="text-lg font-semibold">Create Jira tickets</div>
                <div className="text-sm text-meta">Assign to developer:</div>
                <div className="mt-2 flex gap-2"><Input className="w-[200px]" value={devName} onChange={e=>setDevName((e.target as HTMLInputElement).value)} /><Button>Confirm</Button><Button variant="outline" onClick={()=>setShowConfirm(null)}>Cancel</Button></div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <div><div className="text-lg font-semibold">Create Confluence page</div><div className="text-sm text-meta">Available to all roles</div></div>
              <div className="flex gap-2"><Button>Confirm</Button><Button variant="outline" onClick={()=>setShowConfirm(null)}>Cancel</Button></div>
            </div>
          )}
        </Panel>
      )}
    </div>
  );
}
