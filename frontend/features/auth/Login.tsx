"use client";

import {
  CheckCircle2,
  Eye,
  EyeOff,
  Link2,
  Lock,
  Mail,
  Send,
  Shield,
  User,
  UserRoundPlus,
  UsersRound,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { InputHTMLAttributes, ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { useAuthForm } from "@/features/auth/hooks/use-auth-form";

const benefits = [
  {
    icon: UsersRound,
    title: "Multi-tenant",
    text: "Isolated configs and data per workspace.",
  },
  {
    icon: Send,
    title: "Smart posting",
    text: "Send offers to multiple Telegram destinations.",
  },
  {
    icon: Link2,
    title: "Affiliate ready",
    text: "Convert and track links across marketplaces.",
  },
];

const trustItems = [
  { icon: Lock, text: "Secure by design" },
  { icon: Shield, text: "Your data is private" },
  { icon: Zap, text: "Built for speed" },
];

function Field({
  icon: Icon,
  label,
  action,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & {
  icon: LucideIcon;
  label: string;
  action?: ReactNode;
}) {
  return (
    <label className="block space-y-2">
      <span className="text-sm font-semibold text-slate-100">{label}</span>
      <span className="relative block">
        <Icon
          className="pointer-events-none absolute left-4 top-1/2 size-4 -translate-y-1/2 text-slate-500"
          strokeWidth={1.8}
        />
        <input
          className="h-12 w-full rounded-xl border border-white/15 bg-[#0c1414]/80 pl-11 pr-12 text-sm text-slate-100 outline-none transition placeholder:text-slate-500 focus:border-emerald-400/60 focus:ring-4 focus:ring-emerald-500/10"
          {...props}
        />
        {action}
      </span>
    </label>
  );
}

export function Login() {
  const {
    authMode,
    formState,
    handleGoogleSignIn,
    handleSubmit,
    message,
    setShowPassword,
    showPassword,
    switchAuthMode,
  } = useAuthForm();

  return (
    <main className="relative isolate min-h-[100dvh] overflow-x-hidden bg-[#07110f] text-white">
      <div className="absolute inset-0 -z-30 bg-[radial-gradient(circle_at_0%_0%,rgba(10,135,98,0.62),transparent_36%),radial-gradient(circle_at_94%_96%,rgba(5,165,113,0.46),transparent_34%),linear-gradient(120deg,#07110f_0%,#0a1213_48%,#07110f_100%)]" />
      <div className="absolute inset-0 -z-20 bg-[linear-gradient(115deg,rgba(255,255,255,0.06),transparent_30%,transparent_70%,rgba(255,255,255,0.04))]" />
      <div className="absolute bottom-0 right-0 -z-10 hidden h-72 w-[42rem] bg-[radial-gradient(ellipse_at_bottom_right,rgba(16,185,129,0.18),transparent_68%)] lg:block" />

      <header className="absolute left-4 top-5 z-10 flex items-center gap-3 text-sm font-bold tracking-wide text-white md:left-10 md:top-8 lg:hidden">
        <Send className="size-5 fill-emerald-500 text-emerald-500" />
        <span>TG OFFERS BOT</span>
      </header>

      <section className="mx-auto grid min-h-[100dvh] w-full max-w-[1320px] gap-8 px-3 pb-5 pt-16 md:px-10 md:py-8 lg:grid-cols-[minmax(0,540px)_470px] lg:items-center lg:gap-28 lg:py-12 xl:gap-36">
        <div className="order-2 mx-auto mt-28 w-full max-w-[540px] lg:order-1 lg:mx-0 lg:mt-0">
          <div className="mb-24 hidden items-center gap-3 text-sm font-bold tracking-wide text-white lg:flex">
            <Send className="size-5 fill-emerald-500 text-emerald-500" />
            <span>TG OFFERS BOT</span>
          </div>

          <div className="w-fit rounded-full border border-emerald-400/20 bg-emerald-400/5 px-4 py-2 text-[11px] font-bold uppercase tracking-[0.2em] text-emerald-300 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]">
            Telegram Offers Bot Automation
          </div>

          <h1 className="mt-7 max-w-[500px] text-4xl font-bold leading-[1.12] tracking-[-0.04em] text-slate-100 sm:text-5xl lg:text-[3.45rem]">
            Automate offer delivery. <span className="text-emerald-500">Scale your earnings.</span>
          </h1>

          <p className="mt-6 max-w-[430px] text-base leading-7 text-slate-300">
            Create your workspace, connect destinations, and start delivering offers across Telegram automatically.
          </p>

          <div className="mt-8 space-y-3">
            {benefits.map((benefit) => {
              const Icon = benefit.icon;
              return (
                <div
                  className="group flex items-center gap-4 rounded-2xl border border-white/5 bg-white/[0.035] p-4 shadow-[0_18px_45px_rgba(0,0,0,0.16)] backdrop-blur transition hover:border-emerald-400/20 hover:bg-white/[0.055]"
                  key={benefit.title}
                >
                  <div className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
                    <Icon className="size-5" strokeWidth={1.8} />
                  </div>
                  <div>
                    <h2 className="text-sm font-bold text-white">{benefit.title}</h2>
                    <p className="mt-1 text-sm text-slate-400">{benefit.text}</p>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="mt-8 grid gap-3 text-xs text-slate-400 sm:grid-cols-3">
            {trustItems.map((item) => {
              const Icon = item.icon;
              return (
                <div className="flex items-center gap-2" key={item.text}>
                  <Icon className="size-4 text-emerald-400" strokeWidth={1.8} />
                  <span>{item.text}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="order-1 mx-auto flex min-h-[calc(100dvh-5.25rem)] w-full max-w-[500px] items-center sm:min-h-0 sm:max-w-[470px] lg:order-2">
          <div className="w-full rounded-[1.75rem] border border-emerald-300/20 bg-white/[0.035] p-4 shadow-[0_28px_100px_rgba(0,0,0,0.38),inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur-xl sm:p-9">
          <div className="mb-5 flex flex-col items-center text-center sm:mb-7">
            <div className="hidden size-12 items-center justify-center rounded-xl border border-emerald-300/20 bg-emerald-500/10 text-emerald-400 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] sm:flex">
              <UserRoundPlus className="size-6" strokeWidth={1.8} />
            </div>
            <p className="text-[11px] font-bold uppercase tracking-[0.22em] text-emerald-400 sm:mt-6">
              {authMode === "register" ? "Registration" : "Sign in"}
            </p>
            <h2 className="mt-2 text-2xl font-bold tracking-[-0.04em] text-slate-100 sm:mt-3 sm:text-3xl">
              {authMode === "register" ? "Create your account" : "Welcome back"}
            </h2>
            <p className="mt-2 text-sm text-slate-400 sm:mt-3">
              {authMode === "register"
                ? "Use your email and password to create your workspace."
                : "Sign in with your email and password."}
            </p>
          </div>

          <form className="space-y-4 sm:space-y-5" noValidate onSubmit={handleSubmit}>
            {authMode === "register" ? (
              <Field icon={User} label="Full name" name="fullName" placeholder="Jane Doe" type="text" />
            ) : null}

            <Field
              icon={Mail}
              label="Email"
              name="email"
              placeholder="you@example.com"
              required
              type="email"
            />

            <Field
              action={
                <button
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-2 top-1/2 flex size-8 -translate-y-1/2 items-center justify-center rounded-full text-slate-500 outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/40"
                  onClick={() => setShowPassword((value) => !value)}
                  type="button"
                >
                  {showPassword ? (
                    <EyeOff className="size-4 shrink-0" />
                  ) : (
                    <Eye className="size-4 shrink-0" />
                  )}
                </button>
              }
              icon={Lock}
              label="Password"
              name="password"
              placeholder="At least 8 characters"
              type={showPassword ? "text" : "password"}
            />

            {authMode === "register" ? (
            <div className="rounded-xl border border-emerald-400/10 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100 sm:px-4 sm:py-3 sm:text-sm">
              <p className="font-semibold text-emerald-300">Password must contain:</p>
              <div className="mt-1.5 space-y-1 text-[11px] text-slate-300 sm:mt-2 sm:space-y-1.5 sm:text-xs">
                {[
                  "At least 8 characters",
                  "One uppercase letter",
                  "One number or symbol",
                ].map((rule) => (
                  <div className="flex items-center gap-2" key={rule}>
                    <CheckCircle2 className="size-3.5 text-emerald-400" strokeWidth={2} />
                    <span>{rule}</span>
                  </div>
                ))}
              </div>
            </div>
            ) : null}

            <Button
              className="h-12 w-full bg-emerald-500 px-5 text-sm font-bold text-emerald-950 transition hover:bg-emerald-400 active:translate-y-px disabled:cursor-not-allowed disabled:bg-emerald-700 disabled:text-emerald-950/60"
              disabled={formState === "submitting"}
              size="lg"
              type="submit"
            >
              {formState === "submitting"
                ? authMode === "register"
                  ? "Creating account..."
                  : "Signing in..."
                : authMode === "register"
                  ? "Create account"
                  : "Sign in"}
            </Button>

            {message ? (
              <p
                className={
                  formState === "success"
                    ? "rounded-xl border border-emerald-400/20 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-200"
                    : "rounded-xl border border-red-400/20 bg-red-400/10 px-4 py-3 text-sm text-red-200"
                }
              >
                {message}
              </p>
            ) : null}
          </form>

          <div className="my-6 grid grid-cols-[1fr_auto_1fr] items-center gap-4 text-xs text-slate-500">
            <div className="h-px bg-white/10" />
            <span>OR</span>
            <div className="h-px bg-white/10" />
          </div>

          <Button
            className="flex h-12 w-full items-center justify-center gap-3 border-white/15 bg-transparent px-4 text-sm font-bold text-slate-100 transition hover:border-emerald-400/30 hover:bg-white/[0.04] active:translate-y-px"
            disabled={formState === "submitting"}
            onClick={handleGoogleSignIn}
            size="lg"
            type="button"
            variant="outline"
          >
            <span className="text-base font-black text-emerald-400">G</span>
            Continue with Google
          </Button>

          <p className="mt-7 text-center text-sm text-slate-400">
            {authMode === "register" ? "Already have an account?" : "Need an account?"}{" "}
            <Button
              className="h-auto rounded-none p-0 font-bold text-emerald-400 hover:bg-transparent hover:text-emerald-300 hover:no-underline"
              onClick={() => switchAuthMode(authMode === "register" ? "signin" : "register")}
              type="button"
              variant="link"
            >
              {authMode === "register" ? "Sign in" : "Create account"}
            </Button>
          </p>
          </div>
        </div>
      </section>
    </main>
  );
}
