import { getApiErrorMessage } from "@/lib/api-error-message";
import type { WhatsAppChat, WhatsAppStatus } from "@/features/whatsapp/types";

async function request<T>(path: string, method = "GET"): Promise<T> {
  const response = await fetch(`/api/backend/users/me/whatsapp${path}`, { method, cache: "no-store" });
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
