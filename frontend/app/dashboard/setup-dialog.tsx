"use client";

import { ArrowLeft, ArrowRight, Check, Copy, KeyRound, Loader2, Send, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";

const platformBotUsername = "tgtestoffersbot";

type ProviderType = "amazon" | "shopee" | "mercado_livre" | "aliexpress";

type ConfigSummary = {
  id: number;
  config_type: string;
  config_data?: Record<string, unknown>;
};

type DestinationSummary = {
  id: number;
  chat_id: string;
  enabled: boolean;
};

type ProviderField = {
  key: string;
  label: string;
  placeholder?: string;
  required?: boolean;
};

type Provider = {
  type: ProviderType;
  name: string;
  description: string;
  fields: ProviderField[];
};

type SetupDialogProps = {
  hasEnabledDestination: boolean;
  destinations: DestinationSummary[];
  configs: ConfigSummary[];
};

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

const providers: Provider[] = [
  {
    type: "amazon",
    name: "Amazon",
    description: "Use your affiliate tag plus Amazon session cookie tokens.",
    fields: [
      { key: "amazon_affiliate_tag", label: "Affiliate tag", placeholder: "yourtag-20", required: true },
      { key: "amazon_cookie_header", label: "Cookie header", placeholder: "session-id=...; at-acbbr=...", required: true },
      { key: "amazon_marketplace_id", label: "Marketplace ID", placeholder: "526970" },
    ],
  },
  {
    type: "shopee",
    name: "Shopee",
    description: "Use Shopee Open Platform affiliate credentials.",
    fields: [
      { key: "shopee_app_id", label: "App ID", required: true },
      { key: "shopee_app_secret", label: "App secret", required: true },
    ],
  },
  {
    type: "mercado_livre",
    name: "Mercado Livre",
    description: "Use affiliate tag, browser cookie, and CSRF token.",
    fields: [
      { key: "ml_affiliate_tag", label: "Affiliate tag", required: true },
      { key: "ml_cookie_header", label: "Cookie header", required: true },
      { key: "ml_csrf_token", label: "CSRF token", required: true },
    ],
  },
  {
    type: "aliexpress",
    name: "AliExpress",
    description: "Use AliExpress app credentials and optional tracking ID.",
    fields: [
      { key: "aliexpress_app_key", label: "App key", required: true },
      { key: "aliexpress_app_secret", label: "App secret", required: true },
      { key: "aliexpress_tracking_id", label: "Tracking ID", placeholder: "default" },
    ],
  },
];

function getExistingConfig(configs: ConfigSummary[], providerType: ProviderType) {
  return configs.find((config) => config.config_type === providerType);
}

function getProviderData(provider: Provider, configs: ConfigSummary[]) {
  const existingConfig = getExistingConfig(configs, provider.type);
  return Object.fromEntries(
    provider.fields.map((field) => [
      field.key,
      typeof existingConfig?.config_data?.[field.key] === "string"
        ? existingConfig.config_data[field.key]
        : "",
    ])
  );
}

export function SetupDialog({ hasEnabledDestination, destinations, configs }: SetupDialogProps) {
  const router = useRouter();
  const enabledDestination = destinations.find((destination) => destination.enabled);
  const [open, setOpen] = useState(false);
  const [screen, setScreen] = useState<"destination" | "providers">(
    hasEnabledDestination ? "providers" : "destination"
  );
  const [chatId, setChatId] = useState(enabledDestination?.chat_id ?? "");
  const [selectedProvider, setSelectedProvider] = useState<ProviderType>("amazon");
  const [providerData, setProviderData] = useState<Record<string, string>>(
    getProviderData(providers[0], configs)
  );
  const [status, setStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [savedDestination, setSavedDestination] = useState<DestinationSummary | undefined>(enabledDestination);
  const [savedConfigs, setSavedConfigs] = useState<ConfigSummary[]>(configs);
  const [connectedProviderTypes, setConnectedProviderTypes] = useState<ProviderType[]>(
    configs
      .map((config) => config.config_type)
      .filter((configType): configType is ProviderType =>
        providers.some((provider) => provider.type === configType)
      )
  );

  const hasStartedSetup = hasEnabledDestination || connectedProviderTypes.length > 0;
  const provider = providers.find((item) => item.type === selectedProvider) ?? providers[0];
  const canFinish = connectedProviderTypes.length > 0;
  const canGoToProviders = Boolean(savedDestination?.enabled);

  function openDialog() {
    setScreen(hasEnabledDestination ? "providers" : "destination");
    setStatus("idle");
    setMessage("");
    setOpen(true);
  }

  function closeDialog() {
    setOpen(false);
    setStatus("idle");
    setMessage("");
  }

  function selectProvider(providerType: ProviderType) {
    const nextProvider = providers.find((item) => item.type === providerType) ?? providers[0];
    setSelectedProvider(providerType);
    setProviderData(getProviderData(nextProvider, savedConfigs));
    setStatus("idle");
    setMessage("");
  }

  function goBackToDestination() {
    setScreen("destination");
    setStatus("idle");
    setMessage("");
  }

  function goToProviders() {
    if (!canGoToProviders) {
      setStatus("error");
      setMessage("Save a destination before continuing to affiliate providers.");
      return;
    }

    setScreen("providers");
    setStatus("idle");
    setMessage("");
  }

  async function handleDestinationSubmit(event: FormEvent<HTMLFormElement>) {
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
      const response = await fetch(
        savedDestination
          ? `/api/backend/users/me/destinations/${savedDestination.id}`
          : "/api/backend/users/me/destinations",
        {
        method: savedDestination ? "PUT" : "POST",
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

      const saved = (await response.json()) as DestinationSummary;

      setSavedDestination(saved);
      setStatus("success");
      setMessage("Destination saved. Continue to affiliate providers when ready.");
      setChatId(saved.chat_id);
      router.refresh();
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Could not verify bot access to this destination."
      );
    }
  }

  async function handleProviderSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const missingField = provider.fields.find(
      (field) => field.required && !providerData[field.key]?.trim()
    );
    if (missingField) {
      setStatus("error");
      setMessage(`${missingField.label} is required for ${provider.name}.`);
      return;
    }

    setStatus("saving");
    setMessage("");

    const configData = Object.fromEntries(
      provider.fields
        .map((field) => [field.key, providerData[field.key]?.trim() ?? ""])
        .filter(([, value]) => value)
    );
    const existingConfig = getExistingConfig(savedConfigs, provider.type);

    try {
      const response = await fetch(
        existingConfig
          ? `/api/backend/users/me/configs/${existingConfig.id}`
          : "/api/backend/users/me/configs",
        {
          method: existingConfig ? "PUT" : "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            config_type: provider.type,
            config_data: configData,
          }),
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const detail = data?.detail;
        const detailMessage =
          typeof detail === "string"
            ? detail
            : typeof detail?.message === "string"
              ? detail.message
              : `Could not save ${provider.name} credentials.`;
        throw new Error(detailMessage);
      }

      const savedConfig = (await response.json()) as ConfigSummary;

      setSavedConfigs((current) => [
        ...current.filter((config) => config.config_type !== provider.type),
        savedConfig,
      ]);
      setConnectedProviderTypes((current) =>
        current.includes(provider.type) ? current : [...current, provider.type]
      );
      setProviderData(getProviderData(provider, [savedConfig]));
      setStatus("success");
      setMessage(`${provider.name} connected. You can add another provider or finish setup.`);
      router.refresh();
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof Error
          ? error.message
          : `Could not save ${provider.name} credentials.`
      );
    }
  }

  function finishProviderSetup() {
    if (!canFinish) {
      setStatus("error");
      setMessage("Connect at least one affiliate provider to continue.");
      return;
    }

    setOpen(false);
    setStatus("success");
    setMessage("Affiliate provider connected. Setup steps updated.");
    router.refresh();
  }

  return (
    <>
      <div className="w-full max-w-sm space-y-3">
        <Button
          className="h-12 w-full gap-3 bg-primary px-7 text-base font-bold text-primary-foreground shadow-[0_14px_30px_rgba(22,163,74,0.18)] transition-colors hover:bg-primary/90 active:translate-y-px dark:shadow-none sm:w-[172px]"
          onClick={openDialog}
          type="button"
        >
          {hasStartedSetup ? "Continue setup" : "Start setup"} <ArrowRight className="size-4" />
        </Button>

      </div>

      {open ? (
        <div
          aria-labelledby="setup-dialog-title"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
          role="dialog"
        >
          <div className="flex h-[min(90dvh,760px)] w-full max-w-4xl flex-col overflow-hidden rounded-[2rem] border border-border bg-card text-card-foreground shadow-[0_30px_120px_rgba(15,23,42,0.35)] dark:border-white/10 dark:bg-[#0c1414]">
            <style>{`
              @keyframes setup-screen-slide {
                from { opacity: 0; transform: translateX(18px); }
                to { opacity: 1; transform: translateX(0); }
              }
              .setup-screen-slide { animation: setup-screen-slide .24s ease-out both; }
              @media (prefers-reduced-motion: reduce) {
                .setup-screen-slide { animation: none; }
              }
            `}</style>
            <div className="flex items-start justify-between gap-4 p-5 pb-0">
              <div className="flex min-w-0 items-start gap-3">
                {screen === "providers" ? (
                  <Button
                    aria-label="Back to destination setup"
                    className="mt-0.5 size-10 shrink-0 rounded-full"
                    onClick={goBackToDestination}
                    size="icon"
                    type="button"
                    variant="outline"
                  >
                    <ArrowLeft className="size-4" />
                  </Button>
                ) : null}
                <div className="min-w-0">
                  <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary">
                    {screen === "destination" ? (
                      <Send className="size-3.5" />
                    ) : (
                      <KeyRound className="size-3.5" />
                    )}
                    {screen === "destination" ? "Telegram bot setup" : "Affiliate provider setup"}
                  </div>
                  <h2
                    className="mt-4 text-2xl font-black tracking-tight md:text-3xl"
                    id="setup-dialog-title"
                  >
                    {screen === "destination" ? "Connect your destination" : "Connect affiliate providers"}
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                    {screen === "destination"
                      ? "Add the platform Telegram bot to your destination, then save the destination chat ID."
                      : "Save credentials for at least one provider so the bot can convert product links into your affiliate links."}
                  </p>
                </div>
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

            <div className="flex-1 overflow-y-auto p-5 pt-0">
            {screen === "destination" ? (
              <>
                <div className="setup-screen-slide mt-6 grid gap-4 lg:grid-cols-[1fr_0.95fr]" key="destination-screen">
                  <div className="rounded-3xl border border-border bg-muted/35 p-4 dark:border-white/10 dark:bg-white/[0.03]">
                    <p className="text-sm font-bold">Platform bot instructions</p>
                    <ol className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                      {setupSteps.map((step) => (
                        <li className="flex gap-3" key={step}>
                          <Check className="mt-1 size-4 shrink-0 text-primary" />
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

                <form className="setup-screen-slide mt-5 rounded-3xl border border-primary/20 bg-primary/5 p-4" onSubmit={handleDestinationSubmit}>
                  <label className="block space-y-2">
                    <span className="text-sm font-bold text-card-foreground">
                      Destination chat ID
                    </span>
                    <input
                      className="h-12 w-full rounded-2xl border border-border bg-background px-4 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10 dark:border-white/10 dark:bg-white/[0.04]"
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
                          ? "mt-3 text-sm font-semibold text-primary"
                          : "mt-3 text-sm font-semibold text-destructive"
                      }
                    >
                      {message}
                    </p>
                  ) : null}

                  <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:justify-between">
                    <Button
                      className="h-12 gap-2"
                      disabled={status === "saving"}
                      type="submit"
                      variant="outline"
                    >
                      {status === "saving" ? <Loader2 className="size-4 animate-spin" /> : null}
                      Save destination
                    </Button>
                    <Button
                      className="h-12 gap-2 bg-primary px-6 text-sm font-bold text-primary-foreground hover:bg-primary/90"
                      onClick={goToProviders}
                      type="button"
                    >
                      Continue to providers <ArrowRight className="size-4" />
                    </Button>
                  </div>
                </form>
              </>
            ) : (
              <div className="setup-screen-slide mt-6 grid gap-5 lg:grid-cols-[260px_1fr]" key="providers-screen">
                <div className="space-y-3">
                  <div className="rounded-3xl border border-border bg-muted/35 p-4 dark:border-white/10 dark:bg-white/[0.03]">
                    <p className="text-sm font-bold">Connected providers</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {connectedProviderTypes.length > 0 ? (
                        connectedProviderTypes.map((providerType) => {
                          const connectedProvider = providers.find((item) => item.type === providerType);
                          return (
                            <span
                              className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary"
                              key={providerType}
                            >
                              <Check className="size-3" /> {connectedProvider?.name ?? providerType}
                            </span>
                          );
                        })
                      ) : (
                        <p className="text-sm leading-6 text-muted-foreground">
                          No provider connected yet. Add at least one.
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="grid gap-2">
                    {providers.map((item) => {
                      const isSelected = item.type === selectedProvider;
                      const isConnected = connectedProviderTypes.includes(item.type);

                      return (
                        <button
                          className={
                            isSelected
                              ? "rounded-2xl border border-primary bg-primary/10 p-3 text-left text-sm transition"
                              : "rounded-2xl border border-border bg-background p-3 text-left text-sm transition hover:border-primary/40 hover:bg-muted/50"
                          }
                          key={item.type}
                          onClick={() => selectProvider(item.type)}
                          type="button"
                        >
                          <span className="flex items-center justify-between gap-3 font-bold text-card-foreground">
                            {item.name}
                            {isConnected ? <Check className="size-4 text-primary" /> : null}
                          </span>
                          <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                            {item.description}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="space-y-4">
                  <form className="rounded-3xl border border-border bg-muted/25 p-4 dark:border-white/10 dark:bg-white/[0.03]" onSubmit={handleProviderSubmit}>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-lg font-black tracking-tight">{provider.name}</p>
                        <p className="mt-1 text-sm leading-6 text-muted-foreground">
                          {provider.description}
                        </p>
                      </div>
                      {connectedProviderTypes.includes(provider.type) ? (
                        <span className="w-fit rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary">
                          Connected
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-4 grid gap-3">
                      {provider.fields.map((field) => (
                        <label className="block space-y-2" key={field.key}>
                          <span className="text-sm font-bold text-card-foreground">
                            {field.label}{field.required ? " *" : ""}
                          </span>
                          <input
                            className="h-12 w-full rounded-2xl border border-border bg-background px-4 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10 dark:border-white/10 dark:bg-white/[0.04]"
                            onChange={(event) =>
                              setProviderData((current) => ({
                                ...current,
                                [field.key]: event.target.value,
                              }))
                            }
                            placeholder={field.placeholder}
                            type={field.key.includes("secret") || field.key.includes("cookie") || field.key.includes("token") ? "password" : "text"}
                            value={providerData[field.key] ?? ""}
                          />
                        </label>
                      ))}
                    </div>

                    {message ? (
                      <p
                        className={
                          status === "success"
                            ? "mt-3 text-sm font-semibold text-primary"
                            : "mt-3 text-sm font-semibold text-destructive"
                        }
                      >
                        {message}
                      </p>
                    ) : null}

                    <div className="mt-5 flex justify-start">
                      <Button
                        className="h-12 gap-2"
                        disabled={status === "saving"}
                        type="submit"
                        variant="outline"
                      >
                        {status === "saving" ? <Loader2 className="size-4 animate-spin" /> : null}
                        Save {provider.name}
                      </Button>
                    </div>
                  </form>

                  <div className="flex flex-col gap-3 rounded-3xl border border-primary/15 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm leading-6 text-muted-foreground">
                      {canFinish
                        ? "At least one provider is connected. You can finish setup now or add another provider."
                        : "Connect at least one provider before finishing setup."}
                    </p>
                    <Button
                      className="h-12 gap-2 bg-primary px-6 font-bold text-primary-foreground hover:bg-primary/90"
                      onClick={finishProviderSetup}
                      type="button"
                    >
                      Finish setup <ArrowRight className="size-4" />
                    </Button>
                  </div>
                </div>
              </div>
            )}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
