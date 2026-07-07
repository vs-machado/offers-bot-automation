"use client";

import { ArrowRight, Check, Copy, ExternalLink, Loader2, Send, X } from "lucide-react";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";

const platformBotUsername = "tgtestoffersbot";
const platformBotUrl = `https://t.me/${platformBotUsername}`;

const setupSteps = [
  `Add @${platformBotUsername} to your destination group or channel.`,
  "Promote that bot to admin with permission to post messages and photos.",
  "Paste the destination chat ID below and confirm setup.",
];

const chatIdSteps = [
  "Add @RawDataBot to the group, send any message, then copy the chat.id value.",
  "For channels, forward one channel post to @RawDataBot and copy forward_from_chat.id.",
  "Group and channel IDs often start with -100. Keep the minus sign.",
  "Remove @RawDataBot after copying the ID if you do not want to keep it there.",
];

export function SetupDialog() {
  const [open, setOpen] = useState(false);
  const [chatId, setChatId] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [message, setMessage] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedChatId = chatId.trim();
    if (!trimmedChatId) {
      setStatus("error");
      setMessage("Destination chat ID is required.");
      return;
    }

    setStatus("saving");
    setMessage("");

    try {
      const response = await fetch("/api/backend/users/me/destinations", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          chat_id: trimmedChatId,
          title: null,
          chat_type: "group",
          enabled: true,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const detail = data?.detail;
        throw new Error(
          typeof detail === "string"
            ? detail
            : "Could not verify bot access to this destination."
        );
      }

      setStatus("success");
      setMessage("Destination saved. Bot can post there.");
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not verify bot access to this destination."
      );
    }
  }

  function closeDialog() {
    setOpen(false);
    setStatus("idle");
    setMessage("");
  }

  return (
    <>
      <Button
        className="h-12 w-full max-w-[180px] gap-3 bg-emerald-600 px-7 text-base font-bold text-white shadow-[0_14px_30px_rgba(22,163,74,0.18)] transition-colors hover:bg-emerald-700 active:translate-y-px dark:bg-emerald-500 dark:text-emerald-950 dark:hover:bg-emerald-400 sm:w-[172px]"
        onClick={() => setOpen(true)}
        type="button"
      >
        Start setup <ArrowRight className="size-4" />
      </Button>

      {open ? (
        <div
          aria-labelledby="setup-dialog-title"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
          role="dialog"
        >
          <div className="max-h-[90dvh] w-full max-w-3xl overflow-y-auto rounded-[2rem] border border-border bg-card p-5 text-card-foreground shadow-[0_30px_120px_rgba(15,23,42,0.35)] dark:border-white/10 dark:bg-[#0c1414]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-600 dark:text-emerald-300">
                  <Send className="size-3.5" /> Telegram bot setup
                </div>
                <h2
                  className="mt-4 text-2xl font-black tracking-tight md:text-3xl"
                  id="setup-dialog-title"
                >
                  Connect your destination
                </h2>
                <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
                  Add the platform Telegram bot to your destination, then save the destination chat ID.
                </p>
              </div>
              <Button
                aria-label="Close setup dialog"
                className="size-10 rounded-full"
                onClick={closeDialog}
                size="icon"
                type="button"
                variant="outline"
              >
                <X className="size-4" />
              </Button>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_0.95fr]">
              <div className="rounded-3xl border border-border bg-muted/35 p-4 dark:border-white/10 dark:bg-white/[0.03]">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-bold">Platform bot instructions</p>
                </div>
                <ol className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                  {setupSteps.map((step) => (
                    <li className="flex gap-3" key={step}>
                      <Check className="mt-1 size-4 shrink-0 text-emerald-600 dark:text-emerald-300" />
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="rounded-3xl border border-border bg-muted/35 p-4 dark:border-white/10 dark:bg-white/[0.03]">
                <p className="text-sm font-bold">How to get chat ID</p>
                <ol className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                  {chatIdSteps.map((step) => (
                    <li className="flex gap-3" key={step}>
                      <Copy className="mt-1 size-4 shrink-0 text-sky-600 dark:text-sky-300" />
                      <span>{step}</span>
                    </li>
                  ))}
                </ol>
              </div>
            </div>

            <form className="mt-5 rounded-3xl border border-emerald-500/20 bg-emerald-500/5 p-4" onSubmit={handleSubmit}>
              <label className="block space-y-2">
                <span className="text-sm font-bold text-card-foreground">
                  Destination chat ID
                </span>
                <input
                  className="h-12 w-full rounded-2xl border border-border bg-background px-4 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 dark:border-white/10 dark:bg-white/[0.04]"
                  inputMode="text"
                  onChange={(event) => setChatId(event.target.value)}
                  placeholder="Example: -1001234567890"
                  value={chatId}
                />
              </label>

              {message ? (
                <p
                  className={
                    status === "success"
                      ? "mt-3 text-sm font-semibold text-emerald-600 dark:text-emerald-300"
                      : "mt-3 text-sm font-semibold text-destructive"
                  }
                >
                  {message}
                </p>
              ) : null}

              <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs leading-5 text-muted-foreground">
                  Backend verifies the platform bot can post before enabling this destination.
                </p>
                <Button
                  className="h-12 gap-2 bg-emerald-600 px-6 text-sm font-bold text-white hover:bg-emerald-700 dark:bg-emerald-500 dark:text-emerald-950 dark:hover:bg-emerald-400"
                  disabled={status === "saving"}
                  type="submit"
                >
                  {status === "saving" ? <Loader2 className="size-4 animate-spin" /> : null}
                  Alright, everything&apos;s ready!
                </Button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );
}
