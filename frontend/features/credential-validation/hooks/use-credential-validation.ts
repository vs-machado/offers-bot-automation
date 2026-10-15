"use client";

import { useEffect, useRef, useState } from "react";
import { validateCredentials } from "@/features/credential-validation/api/credential-validation-client";
import { getRequestErrorMessage } from "@/lib/api-error-message";
import type { ProviderType } from "@/lib/affiliate-providers";
import type { CredentialValidationResult } from "@/shared/contracts/affiliate-validation";

export function useCredentialValidation(provider: ProviderType, credentials: Record<string, string>) {
  const [productUrl, setProductUrl] = useState("");
  const [isValidating, setIsValidating] = useState(false);
  const [validation, setValidation] = useState<{ snapshot: string; result?: CredentialValidationResult; error?: string } | null>(null);
  const request = useRef<AbortController | null>(null);
  const values = Object.fromEntries(Object.entries(credentials).map(([key, value]) => [key, value.trim()]));
  const snapshot = JSON.stringify([provider, Object.entries(values).sort(([left], [right]) => left.localeCompare(right)), productUrl.trim()]);
  const currentValidation = validation?.snapshot === snapshot ? validation : null;

  useEffect(() => () => request.current?.abort(), []);

  async function validate() {
    if (request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setIsValidating(true);
    setValidation(null);
    try {
      const result = await validateCredentials(provider, values, productUrl, controller.signal);
      if (!controller.signal.aborted) setValidation({ snapshot, result });
    } catch (cause) {
      if (!controller.signal.aborted) setValidation({ snapshot, error: getRequestErrorMessage(cause, "Não foi possível validar a configuração. Tente novamente mais tarde.") });
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setIsValidating(false);
    }
  }

  return { productUrl, setProductUrl, isValidating, currentValidation, validate };
}
