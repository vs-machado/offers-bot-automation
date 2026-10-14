import type { AdminSourceGroup, SourceGroupInput } from "@/features/admin/types";
import { getApiErrorMessage } from "@/lib/api-error-message";

async function requestCatalog<T>(path: string, method: string, body?: SourceGroupInput): Promise<T> {
  const response = await fetch(`/api/backend/admin/source-groups${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(getApiErrorMessage(data, "Não foi possível salvar o catálogo de grupos. Tente novamente."));
  }
  return data as T;
}

export function saveSourceGroup(input: SourceGroupInput, id?: number) {
  return requestCatalog<AdminSourceGroup>(id === undefined ? "" : `/${id}`, id === undefined ? "POST" : "PUT", input);
}

export function removeSourceGroup(id: number) {
  return requestCatalog<void>(`/${id}`, "DELETE");
}
