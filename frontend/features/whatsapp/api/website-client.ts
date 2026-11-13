import { getApiErrorMessage } from "@/lib/api-error-message";
import type { WebsiteData, WebsiteSettings } from "@/features/whatsapp/website-types";

async function request(path = "", method = "GET", body?: unknown): Promise<WebsiteData> {
  const response = await fetch(`/api/backend/users/me/whatsapp/website${path}`, {
    method, cache: "no-store",
    ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(getApiErrorMessage(data, "Não foi possível atualizar a integração do site."));
  return data as WebsiteData;
}

export const getWebsite = () => request();
export const saveWebsite = (settings: WebsiteSettings) => request("", "PUT", settings);
export const recoverWebsite = (destinationId: number) => request("/recover", "POST", { destination_id: destinationId });
