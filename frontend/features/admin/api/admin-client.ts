import type { AdminSourceGroup, SourceGroupInput } from "@/features/admin/types";

async function requestCatalog<T>(path: string, method: string, body?: SourceGroupInput): Promise<T> {
  const response = await fetch(`/api/backend/admin/source-groups${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    const message = typeof detail === "string"
      ? detail
      : Array.isArray(detail) && typeof detail[0]?.msg === "string"
        ? detail[0].msg
        : "Could not save the source catalog.";
    throw new Error(message);
  }
  return data as T;
}

export function saveSourceGroup(input: SourceGroupInput, id?: number) {
  return requestCatalog<AdminSourceGroup>(id === undefined ? "" : `/${id}`, id === undefined ? "POST" : "PUT", input);
}

export function removeSourceGroup(id: number) {
  return requestCatalog<void>(`/${id}`, "DELETE");
}
