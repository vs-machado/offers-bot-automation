"use client";

import { useRouter } from "next/navigation";
import { type FormEvent, useState } from "react";
import { authClient } from "@/lib/auth-client";
import { getPasswordError } from "@/lib/password-policy";
import { getRequestErrorMessage } from "@/lib/api-error-message";
import { getAuthError } from "@/features/auth/lib/auth-errors";

export type AuthMode = "register" | "signin";
export type AuthFormState = "idle" | "submitting" | "success" | "error";

export function useAuthForm(errorCode?: string, initialMode: AuthMode = "register") {
  const router = useRouter();
  const [authMode, setAuthMode] = useState<AuthMode>(initialMode);
  const [formState, setFormState] = useState<AuthFormState>(errorCode ? "error" : "idle");
  const [message, setMessage] = useState(errorCode ? getAuthError({ code: errorCode }, "Não foi possível entrar. Tente novamente com a opção usada ao criar sua conta.") : "");
  const [showPassword, setShowPassword] = useState(false);

  async function handleGoogleSignIn() {
    setFormState("submitting");
    setMessage("");
    try {
      const result = await authClient.signIn.social({ provider: "google", callbackURL: "/dashboard", errorCallbackURL: "/" });
      if (result.error) throw new Error(getAuthError(result.error, "Não foi possível entrar com o Google. Tente novamente."));
    } catch (cause) {
      setFormState("error");
      setMessage(getRequestErrorMessage(cause, "Não foi possível entrar com o Google."));
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    if (!email || !password) { setFormState("error"); setMessage("Informe seu e-mail e sua senha."); return; }
    if (authMode === "register") {
      const error = getPasswordError(password);
      if (error) { setFormState("error"); setMessage(error); return; }
    }
    setFormState("submitting");
    setMessage("");
    try {
      const result = authMode === "register"
        ? await authClient.signUp.email({ email, password, name: String(form.get("fullName") ?? "").trim() || email.split("@")[0] })
        : await authClient.signIn.email({ email, password });
      if (result.error) throw new Error(getAuthError(result.error, "Não foi possível entrar ou criar sua conta. Tente novamente."));
      setFormState("success");
      setMessage("Tudo certo! Abrindo seu painel…");
      router.push("/dashboard");
      router.refresh();
    } catch (cause) {
      setFormState("error");
      setMessage(getRequestErrorMessage(cause, "Não foi possível entrar na sua conta."));
    }
  }

  function switchAuthMode(mode: AuthMode) {
    setAuthMode(mode); setFormState("idle"); setMessage(""); setShowPassword(false);
  }
  return { authMode, formState, handleGoogleSignIn, handleSubmit, message, setShowPassword, showPassword, switchAuthMode };
}
