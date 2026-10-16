import { getApiErrorMessage } from "@/lib/api-error-message";
import type { ConfigSummary, DestinationSummary } from "@/shared/contracts/user-config";

type SaveConfigInput = {
  configData: Record<string, unknown>;
  configType: string;
  errorMessage: string;
  id?: number;
};

type SaveDestinationInput = {
  chatId: string;
  id?: number;
  platform?: "telegram" | "whatsapp";
  chatType?: string;
  title?: string | null;
};

async function requestJson<T>(url: string, init: RequestInit, errorMessage: string): Promise<T> {
  const response = await fetch(url, init);
  const data = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(getApiErrorMessage(data, errorMessage));
  }

  return data as T;
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

export function saveDestination({ chatId, id, platform = "telegram", chatType = "group", title = null }: SaveDestinationInput) {
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
        title,
        platform,
        chat_type: chatType,
        enabled: true,
      }),
    },
    "Não foi possível verificar o acesso do bot. Confira o ID e as permissões no grupo ou canal."
  );
}
