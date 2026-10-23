import type { Delivery, DeliveryStatus } from "@/features/dashboard/types";

export const deliveryStatusLabels: Record<DeliveryStatus, string> = {
  queued: "Na fila",
  retrying: "Nova tentativa",
  sending: "Enviando",
  sent: "Enviada",
  failed: "Falhou",
  expired: "Expirada",
  cancelled: "Cancelada",
  uncertain: "Sem confirmação",
};

const platformLabels: Record<string, string> = {
  amazon: "Amazon",
  shopee: "Shopee",
  mercado_livre: "Mercado Livre",
  aliexpress: "AliExpress",
  kabum: "KaBuM",
  magalu: "Magalu",
};

export function getPlatformLabel(platform: string | null) {
  return platform ? (platformLabels[platform] ?? platform) : "Não informada";
}

export function formatDeliveryDate(value: string, compact = false) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Data indisponível";
  return new Intl.DateTimeFormat("pt-BR", {
    ...(compact
      ? { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }
      : { dateStyle: "short", timeStyle: "short" }),
    timeZone: "America/Sao_Paulo",
  }).format(date);
}

export function getDeliveryStage(delivery: Delivery) {
  if (delivery.stage === "affiliate") return "Conversão do link";
  if (delivery.stage === "processing") return "Preparação da promoção";
  return delivery.chat_id.endsWith("@newsletter") ||
    delivery.chat_id.endsWith("@g.us")
    ? "Publicação no WhatsApp"
    : "Publicação no Telegram";
}
