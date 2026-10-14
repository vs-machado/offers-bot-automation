import "server-only";

import { getSession } from "@/lib/auth-session";
import { redirect } from "next/navigation";

import type { AdminSourceGroup } from "@/features/admin/types";

export async function getAdminSourceGroups(): Promise<AdminSourceGroup[]> {
  const session = await getSession();
  if (!session?.sessionToken) redirect("/");
  const apiBaseUrl = process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
  // The API checks the current database role, including revocations, on each render.
  const response = await fetch(`${apiBaseUrl}/admin/source-groups`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${session.sessionToken}` },
  });
  if (response.status === 401) redirect("/");
  if (response.status === 403) redirect("/dashboard");
  if (!response.ok) throw new Error("Não foi possível carregar o catálogo de grupos.");
  return response.json() as Promise<AdminSourceGroup[]>;
}
