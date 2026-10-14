import type { ProviderType } from "@/lib/affiliate-providers";
import type { CredentialValidationResult } from "@/shared/contracts/affiliate-validation";
import { getApiErrorMessage } from "@/lib/api-error-message";

export async function validateCredentials(provider: ProviderType, credentials: Record<string, string>, productUrl: string, signal: AbortSignal): Promise<CredentialValidationResult> {
  const response = await fetch("/api/backend/users/me/affiliate-credentials/validate", {
    method: "POST", headers: { "Content-Type": "application/json" }, signal,
    body: JSON.stringify({ provider, config_data: credentials, product_url: productUrl.trim() || null }),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new Error(getApiErrorMessage(data, "Não foi possível validar as credenciais. Tente novamente mais tarde."));
  if (!data) throw new Error("O serviço de validação não retornou um resultado. Tente novamente.");
  return data as CredentialValidationResult;
}
