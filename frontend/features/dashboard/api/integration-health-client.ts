export type IntegrationHealth = {
  whatsapp: "connected" | "disconnected" | "not_configured" | "unknown";
  mercado_livre: "connected" | "expired" | "incomplete" | "not_configured" | "unknown";
};

export async function getIntegrationHealth(signal: AbortSignal): Promise<IntegrationHealth> {
  const response = await fetch("/api/backend/users/me/integration-health", {
    cache: "no-store",
    signal,
  });
  if (!response.ok) throw new Error("Não foi possível verificar as integrações.");
  return response.json();
}
