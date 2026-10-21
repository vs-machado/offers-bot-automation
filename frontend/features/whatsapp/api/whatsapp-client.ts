import { getApiErrorMessage } from "@/lib/api-error-message";
import type { ManagedWhatsAppChat, WhatsAppGroupCreate, WhatsAppGroupDraft, WhatsAppGroupResult, WhatsAppChat, WhatsAppStatus, WhatsAppPolicy, WhatsAppPolicyData, WhatsAppConnectionSummary } from "@/features/whatsapp/types";
import type { DestinationSummary, OfferCategory } from "@/shared/contracts/user-config";

async function request<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`/api/backend/users/me/whatsapp${path}`, { method, cache: "no-store", ...(body === undefined ? {} : { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }) });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(getApiErrorMessage(data, "Não foi possível conectar ao WhatsApp."));
  return data as T;
}

const scoped = (path: string, connectionId?: number) => connectionId === undefined ? path : `${path}?connection_id=${connectionId}`;
export const getWhatsAppConnections = () => request<WhatsAppConnectionSummary[]>("/connections");
export const createWhatsAppConnection = (name: string) => request<WhatsAppConnectionSummary>("/connections", "POST", { name });
export const renameWhatsAppConnection = (id: number, name: string) => request<WhatsAppConnectionSummary>(`/connections/${id}`, "PUT", { name });
export const getWhatsAppStatus = (id?: number) => request<WhatsAppStatus>(scoped("", id));
export const startWhatsApp = (id?: number) => request<WhatsAppStatus>(scoped("", id), "POST");
export const disconnectWhatsApp = (id?: number) => request<void>(scoped("", id), "DELETE");
export const getWhatsAppQr = (id?: number) => request<{ qr: string }>(scoped("/qr", id));
export const getWhatsAppGroups = (id?: number) => request<WhatsAppChat[]>(scoped("/groups", id));
export const getWhatsAppChannels = (id?: number) => request<WhatsAppChat[]>(scoped("/channels", id));
export const getWhatsAppPolicy = (id?: number) => request<WhatsAppPolicyData>(scoped("/policy", id));
export const saveWhatsAppPolicy = (settings: WhatsAppPolicy, id?: number) => request<WhatsAppPolicy>(scoped("/policy", id), "PUT", settings);
export const resumeWhatsAppDeliveries = (id?: number) => request<void>(scoped("/policy/resume", id), "POST");

const chatPath = (chat: Pick<ManagedWhatsAppChat, "id" | "chat_type">) =>
  `/manage/${chat.chat_type === "group" ? "groups" : "channels"}/${encodeURIComponent(chat.id)}`;

export const getManagedWhatsAppGroups = (id?: number) => request<ManagedWhatsAppChat[]>(scoped("/manage/groups", id));
export const getManagedWhatsAppChannels = (id?: number) => request<ManagedWhatsAppChat[]>(scoped("/manage/channels", id));
export const getManagedWhatsAppChat = (chat: ManagedWhatsAppChat, id?: number) => request<ManagedWhatsAppChat>(scoped(chatPath(chat), id));
export const createWhatsAppGroup = (draft: WhatsAppGroupCreate, id?: number) => request<WhatsAppGroupResult>(scoped("/manage/groups", id), "POST", draft);
export const updateWhatsAppGroup = (chat: ManagedWhatsAppChat, draft: WhatsAppGroupDraft, id?: number) => request<WhatsAppGroupResult>(scoped(chatPath(chat), id), "PUT", draft);
export const saveWhatsAppRouting = (chat: ManagedWhatsAppChat, categories: OfferCategory[] | null, enabled: boolean, id?: number) =>
  request<Pick<ManagedWhatsAppChat, "destination_id" | "categories" | "enabled">>(scoped(`${chatPath(chat)}/routing`, id), "PUT", { categories, enabled });

export async function getSavedWhatsAppDestinations(connectionId?: number) {
  const response = await fetch("/api/backend/users/me/destinations", { cache: "no-store" });
  const data = await response.json();
  if (!response.ok) throw new Error(getApiErrorMessage(data, "Não foi possível carregar destinos salvos."));
  return (data as DestinationSummary[]).filter((destination) => destination.platform === "whatsapp" && (connectionId === undefined || destination.connection_id === connectionId));
}

/** Remove routing only; the WhatsApp group or channel is not deleted. */
export async function removeWhatsAppDestination(id: number) {
  const response = await fetch(`/api/backend/users/me/destinations/${id}`, { method: "DELETE" });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(getApiErrorMessage(data, "Não foi possível remover o destino."));
  }
}

/** Reassign routing without activating an account's destinations implicitly. */
export async function moveWhatsAppDestination(chat: ManagedWhatsAppChat, connectionId: number) {
  const response = await fetch(`/api/backend/users/me/destinations/${chat.destination_id}`, {
    method: "PUT", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chat.id, title: chat.name, chat_type: chat.chat_type, platform: "whatsapp", categories: chat.categories, enabled: false, connection_id: connectionId }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(getApiErrorMessage(data, "Não foi possível transferir destino."));
  }
}
