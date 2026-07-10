"use client";

import { signIn } from "next-auth/react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { registerUser } from "@/features/auth/api/register-user";

export type AuthMode = "register" | "signin";
export type AuthFormState = "idle" | "submitting" | "success" | "error";

function getPasswordError(password: string) {
  if (password.length < 8) {
    return "Password must be at least 8 characters.";
  }
  if (!/[A-Z]/.test(password)) {
    return "Password must include one uppercase letter.";
  }
  if (!/[0-9\W_]/.test(password)) {
    return "Password must include one number or symbol.";
  }
  return "";
}

function getEmailError(email: string) {
  if (!email) {
    return "Email is required.";
  }
  if (!/^\S+@\S+\.\S+$/.test(email)) {
    return "Enter a valid email address.";
  }
  return "";
}

export function useAuthForm() {
  const router = useRouter();
  const [authMode, setAuthMode] = useState<AuthMode>("register");
  const [formState, setFormState] = useState<AuthFormState>("idle");
  const [message, setMessage] = useState("");
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
      setMessage("Password is required.");
      return false;
    }

    const result = await signIn("credentials", {
      email,
      password,
      callbackUrl: "/dashboard",
      redirect: false,
    });
    if (result?.error) {
      throw new Error("Incorrect email or password.");
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
          ? "Account created. Redirecting to dashboard..."
          : "Signed in. Redirecting to dashboard..."
      );
      router.push("/dashboard");
      router.refresh();
    } catch (error) {
      setFormState("error");
      setMessage(
        error instanceof Error
          ? error.message
          : authMode === "register"
            ? "Could not create account."
            : "Could not sign in."
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
