import "server-only";

import { getSession } from "@/lib/auth-session";
import { redirect } from "next/navigation";

import type { AdminSourceGroup } from "@/features/admin/types";
import type { BufferState } from "./x-buffer-types";

export async function getAdminSourceGroups(): Promise<AdminSourceGroup[]> {
  return adminGet<AdminSourceGroup[]>("source-groups");
}

export async function getAdminBufferState(): Promise<BufferState> {
  return adminGet<BufferState>("x-buffer");
}

async function adminGet<T>(path: string): Promise<T> {
  const session = await getSession();
  if (!session?.sessionToken) redirect("/");
  const apiBaseUrl = process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
  // The API checks the current database role, including revocations, on each render.
  const response = await fetch(`${apiBaseUrl}/admin/${path}`, {
    cache: "no-store",
    headers: { Authorization: `Bearer ${session.sessionToken}` },
  });
  if (response.status === 401) redirect("/");
  if (response.status === 403) redirect("/dashboard");
  if (!response.ok) throw new Error("Não foi possível carregar a configuração de administração.");
  return response.json() as Promise<T>;
}
