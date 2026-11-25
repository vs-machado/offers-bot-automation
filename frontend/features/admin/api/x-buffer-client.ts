import type { BufferState, BufferWrite, RecentXPosts } from "./x-buffer-types";

async function request<T>(suffix: string, init: RequestInit): Promise<T> {
  const response = await fetch(`/api/backend/admin/x-buffer${suffix}`, init);
  const result = await response.json();
  if (!response.ok) {
    throw new Error(typeof result.detail === "string" ? result.detail : "Confira os dados da integração.");
  }
  return result as T;
}

export function saveBufferSettings(settings: BufferWrite) {
  return request<BufferState>("", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(settings) });
}

export function checkBufferSettings() {
  return request<{ account: string }>("/check", { method: "POST" });
}

export function getRecentXPosts(signal: AbortSignal) {
  return request<RecentXPosts>("/posts", { cache: "no-store", signal });
}
