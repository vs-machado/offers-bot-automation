import "server-only";

import { getServerSession } from "next-auth";
import { redirect } from "next/navigation";
import { authOptions } from "@/auth";
import type { SettingsData } from "@/features/settings/types";

export async function getSettingsData(): Promise<SettingsData> {
  const session = await getServerSession(authOptions);
  if (!session?.accessToken) redirect("/");
  const accessToken = session.accessToken;
  const apiBaseUrl = process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
  async function load<T>(path: string): Promise<T> {
    const response = await fetch(`${apiBaseUrl}/users/me/${path}`, {
      cache: "no-store", headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (response.status === 401) redirect("/");
    if (!response.ok) throw new Error("Não foi possível carregar suas configurações. Tente novamente mais tarde.");
    return response.json() as Promise<T>;
  }
  const [configs, destinations, sources] = await Promise.all([
    load<SettingsData["configs"]>("configs"),
    load<SettingsData["destinations"]>("destinations"),
    load<SettingsData["sources"]>("source-groups"),
  ]);
  return { configs, destinations, sources };
}
