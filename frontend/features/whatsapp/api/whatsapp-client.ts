import { getApiErrorMessage } from "@/lib/api-error-message";
import type { ManagedWhatsAppChat, WhatsAppGroupCreate, WhatsAppGroupDraft, WhatsAppGroupResult, WhatsAppChat, WhatsAppStatus, WhatsAppPolicy, WhatsAppPolicyData } from "@/features/whatsapp/types";
import type { DestinationSummary, OfferCategory } from "@/shared/contracts/user-config";

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api/backend/users/me/whatsapp${path}`, { method, cache: "no-store", ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(getApiErrorMessage(data, "Não foi possível conectar ao WhatsApp."));
  return data as T;
}

export const getWhatsAppStatus = () => request<WhatsAppStatus>("");
export const startWhatsApp = () => request<WhatsAppStatus>("", "POST");
export const disconnectWhatsApp = () => request<void>("", "DELETE");
export const getWhatsAppQr = () => request<{ qr: string }>("/qr");
export const getWhatsAppGroups = () => request<WhatsAppChat[]>("/groups");
export const getWhatsAppChannels = () => request<WhatsAppChat[]>("/channels");
export const getWhatsAppPolicy = () => request<WhatsAppPolicyData>("/policy");
export const saveWhatsAppPolicy = (settings: WhatsAppPolicy) => request<WhatsAppPolicy>("/policy", "PUT", settings);
export const resumeWhatsAppDeliveries = () => request<void>("/policy/resume", "POST");

const chatPath = (chat: Pick<ManagedWhatsAppChat, "id" | "chat_type">) =>
  `/manage/${chat.chat_type === "group" ? "groups" : "channels"}/${encodeURIComponent(chat.id)}`;

export const getManagedWhatsAppGroups = () => request<ManagedWhatsAppChat[]>("/manage/groups");
export const getManagedWhatsAppChannels = () => request<ManagedWhatsAppChat[]>("/manage/channels");
export const getManagedWhatsAppChat = (chat: ManagedWhatsAppChat) => request<ManagedWhatsAppChat>(chatPath(chat));
export const createWhatsAppGroup = (draft: WhatsAppGroupCreate) => request<WhatsAppGroupResult>("/manage/groups", "POST", draft);
export const updateWhatsAppGroup = (chat: ManagedWhatsAppChat, draft: WhatsAppGroupDraft) => request<WhatsAppGroupResult>(chatPath(chat), "PUT", draft);
export const saveWhatsAppRouting = (chat: ManagedWhatsAppChat, categories: OfferCategory[] | null, enabled: boolean) =>
  request<Pick<ManagedWhatsAppChat, "destination_id" | "categories" | "enabled">>(`${chatPath(chat)}/routing`, "PUT", { categories, enabled });

export async function getSavedWhatsAppDestinations() {
  const response = await fetch("/api/backend/users/me/destinations", { cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(getApiErrorMessage(data, "Não foi possível carregar destinos salvos."));
  return (data as DestinationSummary[]).filter((destination) => destination.platform === "whatsapp");
}

/** Remove routing only; the WhatsApp group or channel is not deleted. */
export async function removeWhatsAppDestination(id: number) {
  const response = await fetch(`/api/backend/users/me/destinations/${id}`, { method: "DELETE" });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(getApiErrorMessage(data, "Não foi possível remover o destino."));
  }
}
