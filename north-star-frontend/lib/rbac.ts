import { Role } from "./auth";
export function canView(route: string, role: Role | null): boolean {
  if (!role) return false;
  if (role === "Admin") return true;
  const map: Record<string, Role[]> = {
    "/": ["Admin","PO","BA","Dev"],
    "/guide": ["Admin","PO","BA","Dev"],
    "/intelliself": ["Admin","Dev"],
    "/intellistaff": ["Admin","PO","BA"],
    "/admin/users": ["Admin"],
    "/aurora": ["Admin","PO","BA","Dev"],
    "/audit": ["Admin","PO"]
  };
  const roles = map[route] || [];
  return roles.includes(role);
}
