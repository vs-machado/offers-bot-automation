import { getApiErrorMessage } from "@/lib/api-error-message";
import type { GamingPolicy } from "../types";
import type { DestinationSummary } from "@/shared/contracts/user-config";

async function request<T>(path: string, signal?: AbortSignal, body?: GamingPolicy): Promise<T> {
  const response = await fetch(`/api/backend/users/me/${path}`, {
    method: body ? "PUT" : "GET",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
    signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(getApiErrorMessage(data, "Não foi possível carregar ou salvar o filtro gamer."));
  return data as T;
}

export function getGamingSettings(signal: AbortSignal) {
  return Promise.all([
    request<GamingPolicy>("gaming-policy", signal),
    request<DestinationSummary[]>("destinations", signal),
  ]);
}

export function saveGamingPolicy(policy: GamingPolicy) {
  return request<GamingPolicy>("gaming-policy", undefined, policy);
}
