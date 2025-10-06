"use client";
import { Panel } from "@/components/ui/panel";

export default function AdminUsers() {
  return (
    <Panel className="p-4">
      <div className="text-lg font-semibold mb-2">Users</div>
      <table className="w-full text-sm">
        <thead className="bg-white/5"><tr><th className="px-3 py-2 text-left">ID</th><th className="px-3 py-2 text-left">Username</th><th className="px-3 py-2 text-left">Role</th><th className="px-3 py-2 text-left">Tenant</th></tr></thead>
        <tbody>
          {[{id:1,u:"alice",r:"Admin",t:"tenant-001"},{id:2,u:"bob",r:"PO",t:"tenant-001"}].map(u=> (
            <tr key={u.id} className="border-t border-white/10"><td className="px-3 py-2">{u.id}</td><td className="px-3 py-2">{u.u}</td><td className="px-3 py-2">{u.r}</td><td className="px-3 py-2">{u.t}</td></tr>
          ))}
        </tbody>
      </table>
    </Panel>
  );
}
