import { getApiErrorMessage } from "@/lib/api-error-message";
import type { ConfigSummary, DestinationSummary } from "@/shared/contracts/user-config";
import type { DestinationInput } from "@/features/settings/types";

async function request<T>(path: string, method: string, body?: object): Promise<T> {
  const response = await fetch(`/api/backend/users/me/${path}`, {
    method, headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(getApiErrorMessage(data, "Não foi possível salvar a alteração. Tente novamente."));
  return data as T;
}

export function saveConfig(type: string, data: Record<string, unknown>, id?: number) {
  return request<ConfigSummary>(id ? `configs/${id}` : "configs", id ? "PUT" : "POST", { config_type: type, config_data: data });
}
export function deleteConfig(id: number) {
  return request<void>(`configs/${id}`, "DELETE");
}
export function saveDestination(data: DestinationInput, id?: number) {
  return request<DestinationSummary>(id ? `destinations/${id}` : "destinations", id ? "PUT" : "POST", data);
}
export function deleteDestination(id: number) {
  return request<void>(`destinations/${id}`, "DELETE");
}
