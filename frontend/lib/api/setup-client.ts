import type { ConfigSummary, DestinationSummary, SourceGroup } from "./types";

type SaveConfigInput = {
  configData: Record<string, unknown>;
  configType: string;
  errorMessage: string;
  id?: number;
};

type SaveDestinationInput = {
  chatId: string;
  id?: number;
};

function getErrorMessage(data: unknown, fallback: string) {
  if (!data || typeof data !== "object" || !("detail" in data)) {
    return fallback;
  }

  const detail = data.detail;
  if (typeof detail === "string") {
    return detail;
  }

  if (detail && typeof detail === "object" && "message" in detail) {
    return typeof detail.message === "string" ? detail.message : fallback;
  }

  return fallback;
}

async function requestJson<T>(url: string, init: RequestInit, errorMessage: string): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getErrorMessage(data, errorMessage));
  }

  return data as T;
}

export async function getSourceGroups() {
  const data = await requestJson<{ groups?: SourceGroup[] }>(
    "/api/backend/users/me/source-groups/messages",
    {},
    "Could not load source groups."
  );
  return data.groups ?? [];
}

export async function previewSourceGroup(chat: string) {
  const data = await requestJson<{ groups?: SourceGroup[] }>(
    "/api/backend/users/me/source-groups/preview",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ chat }),
    },
    "Could not preview source group."
  );
  return data.groups?.[0] ?? null;
}

export function saveUserConfig({
  configData,
  configType,
  errorMessage,
  id,
}: SaveConfigInput) {
  return requestJson<ConfigSummary>(
    id ? `/api/backend/users/me/configs/${id}` : "/api/backend/users/me/configs",
    {
      method: id ? "PUT" : "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        config_type: configType,
        config_data: configData,
      }),
    },
    errorMessage
  );
}

export function saveDestination({ chatId, id }: SaveDestinationInput) {
  return requestJson<DestinationSummary>(
    id
      ? `/api/backend/users/me/destinations/${id}`
      : "/api/backend/users/me/destinations",
    {
      method: id ? "PUT" : "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        chat_id: chatId,
        title: null,
        chat_type: "group",
        enabled: true,
      }),
    },
    "Could not verify bot access to this destination."
  );
}
