"use client";

import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { registerUser } from "@/features/auth/api/register-user";

export type AuthMode = "register" | "signin";
export type AuthFormState = "idle" | "submitting" | "success" | "error";

function getPasswordError(password: string) {
  if (password.length < 8) {
    return "Use uma senha com pelo menos 8 caracteres.";
  }
  if (!/[A-Z]/.test(password)) {
    return "Inclua uma letra maiúscula na senha.";
  }
  if (!/[0-9\W_]/.test(password)) {
    return "Inclua um número ou símbolo na senha.";
  }
  return "";
}

function getEmailError(email: string) {
  if (!email) {
    return "Informe seu e-mail.";
  }
  if (!/^\S+@\S+\.\S+$/.test(email)) {
    return "Confira se o e-mail foi digitado corretamente.";
  }
  return "";
}

function getSignInError(code?: string) {
  if (!code) return "";
  if (code === "Configuration") return "O acesso não está disponível no momento. Entre em contato com o administrador.";
  if (code === "OAuthAccountNotLinked") return "Este e-mail já está associado a outra forma de acesso. Entre com a opção que usou ao criar sua conta.";
  if (code === "SessionRequired") return "Sua sessão expirou. Entre novamente.";
  if (code === "CredentialsSignin") return "E-mail ou senha incorretos.";
  return "Não foi possível entrar na sua conta. Tente novamente ou entre com seu e-mail e sua senha.";
}

export function useAuthForm(errorCode?: string) {
  const router = useRouter();
  const [authMode, setAuthMode] = useState<AuthMode>("register");
  const [formState, setFormState] = useState<AuthFormState>(errorCode ? "error" : "idle");
  const [message, setMessage] = useState(() => getSignInError(errorCode));
  const [showPassword, setShowPassword] = useState(false);

  async function register(formData: FormData, email: string, password: string) {
    const passwordError = getPasswordError(password);
    if (passwordError) {
      setFormState("error");
      setMessage(passwordError);
      return false;
    }

    const fullName = String(formData.get("fullName") ?? "").trim();
    await registerUser({
      email,
      full_name: fullName || null,
      password,
    });
    return true;
  }

  async function signInWithCredentials(email: string, password: string) {
    if (!password) {
      setFormState("error");
      setMessage("Informe sua senha.");
      return false;
    }

    const result = await signIn("credentials", {
      email,
      password,
      callbackUrl: "/dashboard",
      redirect: false,
    });
    if (result?.error) {
      throw new Error("E-mail ou senha incorretos.");
    }
    return true;
  }

  async function handleGoogleSignIn() {
    setFormState("submitting");
    setMessage("");
    await signIn("google", { callbackUrl: "/dashboard" });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const email = String(formData.get("email") ?? "").trim();
    const password = String(formData.get("password") ?? "");
    const emailError = getEmailError(email);

    if (emailError) {
      setFormState("error");
      setMessage(emailError);
      return;
    }

    setFormState("submitting");
    setMessage("");

    try {
      if (authMode === "register" && !(await register(formData, email, password))) {
        return;
      }
      if (!(await signInWithCredentials(email, password))) {
        return;
      }

      setFormState("success");
      setMessage(
        authMode === "register"
          ? "Conta criada! Abrindo seu painel…"
          : "Você entrou! Abrindo seu painel…"
      );
      router.push("/dashboard");
      router.refresh();
    } catch (error) {
      setFormState("error");
      setMessage(
        error instanceof TypeError
          ? "Não foi possível conectar. Confira sua conexão e tente novamente."
          : error instanceof Error
          ? error.message
          : authMode === "register"
            ? "Não foi possível criar sua conta. Tente novamente."
            : "Não foi possível entrar. Tente novamente."
      );
    }
  }

  function switchAuthMode(mode: AuthMode) {
    setAuthMode(mode);
    setFormState("idle");
    setMessage("");
    setShowPassword(false);
  }

  return {
    authMode,
    formState,
    handleGoogleSignIn,
    handleSubmit,
    message,
    setShowPassword,
    showPassword,
    switchAuthMode,
  };
}
