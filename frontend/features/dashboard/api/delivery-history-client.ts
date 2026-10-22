import type { DeliveryHistoryData, DeliveryStatus } from "@/features/dashboard/types";

export async function getDeliveryHistory(page: number, status: DeliveryStatus | "", signal: AbortSignal, platform = ""): Promise<DeliveryHistoryData> {
  const query = new URLSearchParams({ page: String(page), limit: "20", group_by_offer: "true" });
  if (status) query.set("status", status);
  if (platform) query.set("platform", platform);
  const response = await fetch(`/api/backend/users/me/deliveries?${query}`, { cache: "no-store", signal });
  if (!response.ok) {
    throw new Error(response.status === 401 ? "Sua sessão expirou. Entre novamente para consultar o histórico." : "Não foi possível carregar o histórico. Tente atualizar novamente.");
  }
  return response.json() as Promise<DeliveryHistoryData>;
}
