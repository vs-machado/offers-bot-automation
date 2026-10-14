"use client";

import { type FormEvent, useState, useSyncExternalStore } from "react";
import { authClient } from "@/lib/auth-client";
import { getPasswordError } from "@/lib/password-policy";
import { getRequestErrorMessage } from "@/lib/api-error-message";
import { getAuthError } from "@/features/auth/lib/auth-errors";

function subscribeHash(callback: () => void) {
  window.addEventListener("hashchange", callback);
  return () => window.removeEventListener("hashchange", callback);
}
function readToken() { return new URLSearchParams(window.location.hash.slice(1)).get("token") ?? ""; }
function subscribeReady() { return () => {}; }

export function usePasswordRecovery(mode: "request" | "reset") {
  const token = useSyncExternalStore(subscribeHash, readToken, () => "");
  const isReady = useSyncExternalStore(subscribeReady, () => true, () => false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setError("");
    if (mode === "reset") {
      const password = String(data.get("password") ?? "");
      const message = getPasswordError(password);
      if (message) { setError(message); return; }
      if (password !== data.get("confirmation")) { setError("As senhas não são iguais. Digite novamente."); return; }
      if (!token) { setError("Este link não é válido. Solicite um novo link."); return; }
    }
    setIsSubmitting(true);
    try {
      const result = mode === "request"
        ? await authClient.requestPasswordReset({ email: String(data.get("email") ?? "").trim(), redirectTo: "/reset-password" })
        : await authClient.resetPassword({ token, newPassword: String(data.get("password") ?? "") });
      if (result.error) throw new Error(getAuthError(result.error, "Não foi possível concluir o pedido. Tente novamente mais tarde."));
      if (mode === "reset") await authClient.signOut().catch(() => undefined);
      setIsSuccess(true);
    } catch (cause) { setError(getRequestErrorMessage(cause, "Não foi possível conectar ao servidor.")); }
    finally { setIsSubmitting(false); }
  }
  return { token, isReady, isSubmitting, isSuccess, error, submit };
}
