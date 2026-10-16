import type { SourceGroup } from "@/features/source-groups/types";
import { getApiErrorMessage } from "@/lib/api-error-message";

/** Load the available catalog with real recent Telegram messages. */
export async function getSourceGroups(signal?: AbortSignal) {
  const response = await fetch("/api/backend/users/me/source-groups/messages", { signal });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(getApiErrorMessage(data, "Não foi possível carregar os grupos de origem."));
  }
  if (!data || !Array.isArray(data.groups)) {
    throw new Error("Não foi possível carregar os grupos de origem.");
  }
  return data.groups as SourceGroup[];
}
