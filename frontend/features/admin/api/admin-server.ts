import "server-only";

import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";

import { authOptions } from "@/auth";
import type { AdminSourceGroup } from "@/features/admin/types";

export async function getAdminSourceGroups(): Promise<AdminSourceGroup[]> {
  const session = await getServerSession(authOptions);
  if (!session?.accessToken) redirect("/");
  const apiBaseUrl = process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
  // The API checks the current database role, including revocations, on each render.
  const response = await fetch(`${apiBaseUrl}/admin/source-groups`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${session.accessToken}` },
  });
  if (response.status === 401) redirect("/");
  if (response.status === 403) redirect("/dashboard");
  if (!response.ok) throw new Error("Não foi possível carregar o catálogo de grupos.");
  return response.json() as Promise<AdminSourceGroup[]>;
}
