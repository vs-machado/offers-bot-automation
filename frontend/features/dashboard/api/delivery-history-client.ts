import type { DeliveryHistoryData, DeliveryStatus } from "@/features/dashboard/types";

export async function getDeliveryHistory(page: number, status: DeliveryStatus | "", signal: AbortSignal, platform = "", search = ""): Promise<DeliveryHistoryData> {
  const query = new URLSearchParams({ page: String(page), limit: "20", group_by_offer: "true" });
  if (status) query.set("status", status);
  if (platform) query.set("platform", platform);
  if (search) query.set("search", search);
  const response = await fetch(`/api/backend/users/me/deliveries?${query}`, { cache: "no-store", signal });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Sua sessão expirou. Entre novamente para consultar o histórico." : "Não foi possível carregar o histórico. Tente atualizar novamente.");
  }
  return response.json() as Promise<DeliveryHistoryData>;
}

export async function repostDelivery(deliveryId: string, chatId: string): Promise<void> {
  const response = await fetch(
    `/api/backend/users/me/deliveries/${encodeURIComponent(deliveryId)}/repost`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chat_id: chatId }),
    },
  );
  if (response.status === 401) {
    throw new Error("Sua sessão expirou. Entre novamente para publicar a oferta.");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(
      (data as { detail?: string } | null)?.detail ||
        "Não foi possível publicar a oferta agora. Tente novamente.",
    );
  }
}
