import { getApiErrorMessage } from "@/lib/api-error-message";
import type { ConfigSummary } from "@/shared/contracts/user-config";

export async function saveNvidiaModels(primary: string, secondary: string, id?: number) {
  const response = await fetch(`/api/backend/users/me/configs${id ? `/${id}` : ""}`, {
    method: id ? "PUT" : "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config_type: "nvidia_models", config_data: { primary, secondary } }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(getApiErrorMessage(data, "Não foi possível salvar os modelos."));
  return data as ConfigSummary;
}
