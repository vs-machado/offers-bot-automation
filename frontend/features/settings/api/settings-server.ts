import "server-only";

import { getSession } from "@/lib/auth-session";
import { redirect } from "next/navigation";
import type { NvidiaCatalog, SettingsData, SettingsSection } from "@/features/settings/types";

async function getSettingsLoader() {
  const session = await getSession();
  if (!session?.sessionToken) redirect("/");
  const accessToken = session.sessionToken;
  const apiBaseUrl =
    process.env.API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
  return async function load<T>(path: string): Promise<T> {
    const response = await fetch(`${apiBaseUrl}/users/me/${path}`, {
      cache: "no-store",
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (response.status === 401) redirect("/");
    if (!response.ok)
      throw new Error(
        "Não foi possível carregar suas configurações. Tente novamente mais tarde.",
      );
    return response.json() as Promise<T>;
  };
}

export async function getSettingsData(
  section: SettingsSection,
): Promise<SettingsData> {
  const load = await getSettingsLoader();
  const [configs, destinations, sources] = await Promise.all([
    section !== "destinations" ? load<SettingsData["configs"]>("configs") : [],
    section === "destinations"
      ? load<SettingsData["destinations"]>("destinations")
      : [],
    section === "sources" ? load<SettingsData["sources"]>("source-groups") : [],
  ]);
  return { configs, destinations, sources };
}

export async function getPostingModelSettings() {
  const load = await getSettingsLoader();
  const [configs, catalog] = await Promise.all([
    load<SettingsData["configs"]>("configs"),
    load<NvidiaCatalog>("nvidia-models"),
  ]);
  const config = configs.find(({ config_type }) => config_type === "nvidia_models");
  return { catalog, config };
}
