"use client";

import { ArrowLeft, ArrowRight, Check, Copy, KeyRound, Loader2, Send, X } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { getRequestErrorMessage } from "@/lib/api-error-message";
import { saveDestination, saveUserConfig } from "@/features/setup/api/setup-client";
import { LinkedText } from "@/features/setup/components/LinkedText";
import {
  MessagePreviewSkeleton,
  SourceGroupsSkeleton,
} from "@/features/setup/components/SourcePreviewSkeletons";
import { TelegramPostEmbed } from "@/features/setup/components/TelegramPostEmbed";
import { useSourceGroupPreviews } from "@/features/setup/hooks/use-source-group-previews";
import {
  getExistingConfig,
  getProviderData,
  affiliateProviders as providers,
  type ProviderType,
} from "@/lib/affiliate-providers";
import {
  getHiddenMessageLinks,
  getSourceDisplayLabel,
} from "@/features/setup/lib/source-messages";
import { getTelegramPostId } from "@/features/setup/lib/telegram";
import type { ConfigSummary, DestinationSummary, DestinationInput } from "@/shared/contracts/user-config";
import { WhatsAppConnection } from "@/features/whatsapp/WhatsAppConnection";
import { CredentialValidation } from "@/features/credential-validation/CredentialValidation";

const platformBotUsername = "tgtestoffersbot";

type SetupDialogProps = {
  hasEnabledDestination: boolean;
  destinations: DestinationSummary[];
  configs: ConfigSummary[];
};

const setupSteps = [
  `Adicione @${platformBotUsername} ao grupo ou canal onde quer publicar as ofertas.`,
  "Torne o bot administrador e permita que ele envie mensagens e fotos.",
  "Cole abaixo o ID do grupo ou canal e salve a configuração.",
];

const chatIdSteps = [
  "Adicione @RawDataBot ao grupo, envie uma mensagem e copie o valor de chat.id.",
  "Se for um canal, encaminhe uma publicação para @RawDataBot e copie forward_from_chat.id.",
  "Os IDs de grupos e canais geralmente começam com -100. Mantenha o sinal de menos.",
  "Depois de copiar o ID, você pode remover @RawDataBot do grupo.",
];


export function SetupDialog({ hasEnabledDestination, destinations, configs }: SetupDialogProps) {
  const router = useRouter();
  const enabledDestination = destinations.find((destination) => destination.enabled);
  const telegramDestination = destinations.find((destination) => destination.enabled && destination.platform !== "whatsapp");
  const [open, setOpen] = useState(false);
  const [screen, setScreen] = useState<"destination" | "providers" | "sources">(
    hasEnabledDestination ? "providers" : "destination"
  );
  const [chatId, setChatId] = useState(telegramDestination?.chat_id ?? "");
  const [destinationPlatform, setDestinationPlatform] = useState<"telegram" | "whatsapp">(enabledDestination?.platform ?? "telegram");
  const [telegramChatType, setTelegramChatType] = useState(telegramDestination?.chat_type ?? "group");
  const [selectedProvider, setSelectedProvider] = useState<ProviderType>("amazon");
  const [providerData, setProviderData] = useState<Record<string, string>>(
    getProviderData(providers[0], configs)
  );
  const [status, setStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  const [isCompleting, setIsCompleting] = useState(false);
  const [savedDestination, setSavedDestination] = useState<DestinationSummary | undefined>(enabledDestination);
  const [savedConfigs, setSavedConfigs] = useState<ConfigSummary[]>(configs);
  const [connectedProviderTypes, setConnectedProviderTypes] = useState<ProviderType[]>(
    configs
      .map((config) => config.config_type)
      .filter((configType): configType is ProviderType =>
        providers.some((provider) => provider.type === configType)
      )
  );
  const {
    activeSourceGroup,
    markTelegramPostReady,
    mountedSourceGroupIds,
    readyTelegramPostIds,
    selectSourceGroup,
    selectedSourceChats,
    sourceGroups,
    sourceGroupsLoading,
    toggleSourceChat,
  } = useSourceGroupPreviews({ configs, open, screen });

  const hasStartedSetup = hasEnabledDestination || connectedProviderTypes.length > 0;
  const provider = providers.find((item) => item.type === selectedProvider) ?? providers[0];
  const canFinish = connectedProviderTypes.length > 0;
  const canGoToProviders = Boolean(savedDestination?.enabled);
  const canSaveSources = selectedSourceChats.length > 0;
  const headerLabel =
    screen === "destination"
      ? "Telegram e WhatsApp"
      : screen === "providers"
        ? "Programas de afiliados"
        : "Grupos de origem";
  const headerTitle =
    screen === "destination"
      ? "Escolha onde publicar as ofertas"
      : screen === "providers"
        ? "Configure seus programas de afiliados"
        : "Escolha de quais grupos copiar ofertas";
  const headerDescription =
    screen === "destination"
      ? "Escolha Telegram ou WhatsApp e conecte um grupo ou canal para receber ofertas."
      : screen === "providers"
        ? "Configure pelo menos um programa de afiliados para que o bot use seus links nas ofertas."
        : "Veja as mensagens recentes e escolha de quais grupos o bot deve copiar as ofertas.";

  function openDialog() {
    setScreen(hasEnabledDestination ? "providers" : "destination");
    setStatus("idle");
    setMessage("");
    setOpen(true);
  }

  function closeDialog() {
    setOpen(false);
    setIsCompleting(false);
    setStatus("idle");
    setMessage("");
  }

  useEffect(() => {
    if (!isCompleting) {
      return;
    }

    const completionTimeout = window.setTimeout(() => {
      setOpen(false);
      setIsCompleting(false);
      setStatus("idle");
      setMessage("");
      router.refresh();
    }, 1800);

    return () => window.clearTimeout(completionTimeout);
  }, [isCompleting, router]);

  function selectProvider(providerType: ProviderType) {
    const nextProvider = providers.find((item) => item.type === providerType) ?? providers[0];
    setSelectedProvider(providerType);
    setProviderData(getProviderData(nextProvider, savedConfigs));
    setStatus("idle");
    setMessage("");
  }

  function goBackToDestination() {
    setScreen(screen === "sources" ? "providers" : "destination");
    setStatus("idle");
    setMessage("");
  }

  function goToProviders() {
    if (!canGoToProviders) {
      setStatus("error");
      setMessage("Salve o grupo ou canal de publicação antes de configurar seus afiliados.");
      return;
    }

    setScreen("providers");
    setStatus("idle");
    setMessage("");
  }

  function goToSources() {
    if (!canFinish) {
      setStatus("error");
      setMessage("Configure pelo menos um programa de afiliados antes de escolher os grupos de origem.");
      return;
    }

    setScreen("sources");
    setStatus("idle");
    setMessage("");
  }

  async function saveSourceGroups() {
    if (!canSaveSources) {
      setStatus("error");
      setMessage("Selecione pelo menos um grupo de origem.");
      return;
    }

    setStatus("saving");
    setMessage("");

    const existingConfig = savedConfigs.find((config) => config.config_type === "source_chats");

    try {
      const savedConfig = await saveUserConfig({
        configData: { source_chats: selectedSourceChats },
        configType: "source_chats",
        errorMessage: "Não foi possível salvar os grupos de origem. Tente novamente.",
        id: existingConfig?.id,
      });
      setSavedConfigs((current) => [
        ...current.filter((config) => config.config_type !== "source_chats"),
        savedConfig,
      ]);
      setStatus("success");
      setMessage("Tudo pronto! O bot vai copiar as ofertas dos grupos escolhidos.");
      setIsCompleting(true);
    } catch (error) {
      setStatus("error");
      setMessage(getRequestErrorMessage(error, "Não foi possível salvar os grupos de origem. Tente novamente."));
    }
  }

  async function handleDestinationSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedChatId = chatId.trim();
    if (!trimmedChatId) {
      setStatus("error");
      setMessage("Informe o ID do grupo ou canal onde as ofertas serão publicadas.");
      return;
    }

    setStatus("saving");
    setMessage("");

    try {
      const saved = await saveDestination({
        chatId: trimmedChatId,
        id: (savedDestination?.platform ?? "telegram") === "telegram" ? savedDestination?.id : telegramDestination?.id,
        chatType: telegramChatType,
      });

      setSavedDestination(saved);
      setStatus("success");
      setMessage("Grupo ou canal salvo! Agora configure seus programas de afiliados.");
      setChatId(saved.chat_id);
      router.refresh();
    } catch (error) {
      setStatus("error");
      setMessage(
        getRequestErrorMessage(error, "Não foi possível verificar o acesso do bot. Confira o ID e as permissões no grupo ou canal.")
      );
    }
  }

  async function saveWhatsAppDestination(input: DestinationInput) {
    setStatus("saving");
    setMessage("");
    try {
      const saved = await saveDestination({ chatId: input.chat_id, chatType: input.chat_type, title: input.title, platform: "whatsapp" });
      setSavedDestination(saved);
      setStatus("success");
      setMessage("Destino WhatsApp salvo! Agora configure seus programas de afiliados.");
      router.refresh();
      return true;
    } catch (error) {
      setStatus("error");
      setMessage(getRequestErrorMessage(error, "Não foi possível salvar destino WhatsApp."));
      return false;
    }
  }

  async function handleProviderSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const missingField = provider.fields.find(
      (field) => field.required && !providerData[field.key]?.trim()
    );
    if (missingField) {
      setStatus("error");
      setMessage(`Preencha o campo “${missingField.label}” para configurar ${provider.name}.`);
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
      const savedConfig = await saveUserConfig({
        configData,
        configType: provider.type,
        errorMessage: `Não foi possível salvar as credenciais de ${provider.name}. Tente novamente.`,
        id: existingConfig?.id,
      });

      setSavedConfigs((current) => [
        ...current.filter((config) => config.config_type !== provider.type),
        savedConfig,
      ]);
      setConnectedProviderTypes((current) =>
        current.includes(provider.type) ? current : [...current, provider.type]
      );
      setProviderData(getProviderData(provider, [savedConfig]));
      setStatus("success");
      setMessage(`${provider.name} configurado! Você pode configurar outro programa ou escolher os grupos de origem.`);
      router.refresh();
    } catch (error) {
      setStatus("error");
      setMessage(
        getRequestErrorMessage(error, `Não foi possível salvar as credenciais de ${provider.name}. Tente novamente.`)
      );
    }
  }

  function finishProviderSetup() {
    if (!canFinish) {
      setStatus("error");
      setMessage("Configure pelo menos um programa de afiliados para continuar.");
      return;
    }

    goToSources();
  }

  return (
    <>
      <div className="w-full max-w-sm space-y-3">
        <Button
          className="h-12 w-full gap-3 bg-primary px-7 text-base font-bold text-primary-foreground shadow-[0_14px_30px_rgba(22,163,74,0.18)] transition-colors hover:bg-primary/90 active:translate-y-px dark:shadow-none sm:w-43"
          onClick={openDialog}
          type="button"
        >
          {hasStartedSetup ? "Continuar" : "Começar"} <ArrowRight className="size-4" />
        </Button>

      </div>

      {open ? (
        <div
          aria-labelledby="setup-dialog-title"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
          role="dialog"
        >
          <div
            className={`relative flex w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-border bg-card text-card-foreground shadow-[0_30px_120px_rgba(15,23,42,0.35)] dark:border-white/10 dark:bg-[#0c1414] ${
              screen === "sources" ? "h-[min(94dvh,880px)]" : "max-h-[min(94dvh,880px)]"
            }`}
          >
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
                {screen !== "destination" ? (
                  <Button
                    aria-label="Voltar à etapa anterior"
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
                  {screen !== "sources" ? (
                    <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary">
                      {screen === "destination" ? (
                        <Send className="size-3.5" />
                      ) : (
                        <KeyRound className="size-3.5" />
                      )}
                      {headerLabel}
                    </div>
                  ) : null}
                  <h2
                    className={
                      screen === "sources"
                        ? "text-2xl font-black tracking-tight md:text-3xl"
                        : "mt-4 text-2xl font-black tracking-tight md:text-3xl"
                    }
                    id="setup-dialog-title"
                  >
                    {headerTitle}
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm/6 text-muted-foreground">
                    {headerDescription}
                  </p>
                </div>
              </div>
              <Button
                aria-label="Fechar configuração"
                className="size-10 rounded-full"
                onClick={closeDialog}
                size="icon"
                type="button"
                variant="outline"
              >
                <X className="size-4" />
              </Button>
            </div>

            <div className={screen === "sources" ? "flex-1 overflow-hidden p-5 pt-0" : "flex-1 overflow-y-auto p-5 pt-0"}>
            {screen === "destination" ? (
              <>
                <div className="mt-6 flex gap-3" role="group" aria-label="Plataforma de publicação">
                  <Button variant={destinationPlatform === "telegram" ? "default" : "outline"} aria-pressed={destinationPlatform === "telegram"} disabled={status === "saving"} onClick={() => { setDestinationPlatform("telegram"); setStatus("idle"); setMessage(""); }}>Telegram</Button>
                  <Button variant={destinationPlatform === "whatsapp" ? "default" : "outline"} aria-pressed={destinationPlatform === "whatsapp"} disabled={status === "saving"} onClick={() => { setDestinationPlatform("whatsapp"); setStatus("idle"); setMessage(""); }}>WhatsApp</Button>
                </div>
                {destinationPlatform === "whatsapp" ? <div className="mt-5 space-y-4 rounded-3xl border border-border p-4">
                  <h3 className="font-bold">Conectar WhatsApp e selecionar grupo ou canal</h3>
                  <p className="text-sm/6 text-muted-foreground">Conecte sua conta pelo QR. Depois escolha um grupo onde pode enviar mensagens ou um canal que administra. Não precisa copiar IDs.</p>
                  <WhatsAppConnection destinations={[...destinations, ...(savedDestination && !destinations.some((destination) => destination.id === savedDestination.id) ? [savedDestination] : [])]} saveDestination={saveWhatsAppDestination} busy={status === "saving"} />
                  {message ? <p role="status" className={status === "error" ? "text-sm text-destructive" : "text-sm text-primary"}>{message}</p> : null}
                  <Button disabled={!canGoToProviders || status === "saving"} onClick={goToProviders}>Configurar afiliados <ArrowRight className="size-4" /></Button>
                </div> : <>
                <div className="setup-screen-slide mt-6 grid gap-4 lg:grid-cols-[1fr_0.95fr]" key="destination-screen">
                  <div className="rounded-3xl border border-border bg-muted/35 p-4 dark:border-white/10 dark:bg-white/3">
                    <p className="text-sm font-bold">Como adicionar o bot</p>
                    <ol className="mt-4 space-y-3 text-sm/6 text-muted-foreground">
                      {setupSteps.map((step) => (
                        <li className="flex gap-3" key={step}>
                          <Check className="mt-1 size-4 shrink-0 text-primary" />
                          <span>{step}</span>
                        </li>
                      ))}
                    </ol>
                  </div>

                  <div className="rounded-3xl border border-border bg-muted/35 p-4 dark:border-white/10 dark:bg-white/3">
                    <p className="text-sm font-bold">Como encontrar o ID do grupo ou canal</p>
                    <ol className="mt-4 space-y-3 text-sm/6 text-muted-foreground">
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
                  <label className="mb-4 block space-y-2 text-sm font-bold">Tipo de destino Telegram<select className="h-12 w-full rounded-2xl border border-border bg-background px-4" value={telegramChatType} onChange={(event) => setTelegramChatType(event.target.value)}><option value="group">Grupo</option><option value="channel">Canal</option></select></label>
                  <label className="block space-y-2">
                    <span className="text-sm font-bold text-card-foreground">
                      ID do grupo ou canal de publicação
                    </span>
                    <input
                      className="h-12 w-full rounded-2xl border border-border bg-background px-4 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10 dark:border-white/10 dark:bg-white/4"
                      inputMode="text"
                      onChange={(event) => setChatId(event.target.value)}
                      placeholder="Exemplo: -1001234567890"
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
                      Salvar grupo ou canal
                    </Button>
                    <Button
                      className="h-12 gap-2 bg-primary px-6 text-sm font-bold text-primary-foreground hover:bg-primary/90"
                      onClick={goToProviders}
                      type="button"
                    >
                      Configurar afiliados <ArrowRight className="size-4" />
                    </Button>
                  </div>
                </form>
                </>}
              </>
            ) : screen === "providers" ? (
              <div className="setup-screen-slide mt-6 grid gap-5 lg:grid-cols-[260px_1fr]" key="providers-screen">
                <div className="space-y-3">
                  <div className="rounded-3xl border border-border bg-muted/35 p-4 dark:border-white/10 dark:bg-white/3">
                    <p className="text-sm font-bold">Programas configurados</p>
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
                        <p className="text-sm/6 text-muted-foreground">
                          Nenhum programa de afiliados configurado ainda. Escolha um para começar.
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
                          <span className="mt-1 block text-xs/5 text-muted-foreground">
                            {item.description}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="space-y-4">
                  <form className="rounded-3xl border border-border bg-muted/25 p-4 dark:border-white/10 dark:bg-white/3" onSubmit={handleProviderSubmit}>
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-lg font-black tracking-tight">{provider.name}</p>
                        <p className="mt-1 text-sm/6 text-muted-foreground">
                          {provider.description}
                        </p>
                      </div>
                      {connectedProviderTypes.includes(provider.type) ? (
                        <span className="w-fit rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary">
                          Configurado
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
                            className="h-12 w-full rounded-2xl border border-border bg-background px-4 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10 dark:border-white/10 dark:bg-white/4"
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
                        Salvar {provider.name}
                      </Button>
                    </div>
                  </form>

                  <CredentialValidation key={provider.type} provider={provider.type} credentials={providerData} disabled={status === "saving"} />
                  <div className="flex flex-col gap-3 rounded-3xl border border-primary/15 bg-primary/5 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm/6 text-muted-foreground">
                      {canFinish
                        ? "Você já configurou um programa de afiliados. Agora escolha os grupos de origem das ofertas."
                        : "Configure pelo menos um programa de afiliados para continuar."}
                    </p>
                    <Button
                      className="h-12 gap-2 bg-primary px-6 font-bold text-primary-foreground hover:bg-primary/90"
                      onClick={finishProviderSetup}
                      type="button"
                    >
                      Escolher grupos de origem <ArrowRight className="size-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="setup-screen-slide mt-6 grid h-[calc(100%-1.5rem)] min-h-0 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]" key="sources-screen">
                <div className="flex min-h-0 flex-col overflow-hidden rounded-3xl border border-border bg-muted/25 dark:border-white/10 dark:bg-white/3">
                  <div className="border-b border-border p-4 dark:border-white/10">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-bold">Grupos de origem</p>
                      <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary">
                        {selectedSourceChats.length} {selectedSourceChats.length === 1 ? "selecionado" : "selecionados"}
                      </span>
                    </div>
                    <p className="mt-1 text-xs/5 text-muted-foreground">
                      Confira as mensagens recentes de cada grupo e marque os que quer acompanhar.
                    </p>
                  </div>

                  <div className="min-h-0 flex-1 overflow-y-auto p-2">
                    {sourceGroupsLoading ? (
                      <SourceGroupsSkeleton />
                    ) : sourceGroups.length > 0 ? (
                      <div className="space-y-1">
                        {sourceGroups.map((group) => {
                          const selected = selectedSourceChats.includes(group.id);
                          const active = activeSourceGroup?.id === group.id;
                          const displayLabel = getSourceDisplayLabel(group);

                          return (
                            <div
                              className={
                                active
                                  ? "flex items-center gap-2 rounded-2xl border border-primary/30 bg-primary/10 p-2 transition"
                                  : "flex items-center gap-2 rounded-2xl border border-transparent p-2 transition hover:border-border hover:bg-background/70 dark:hover:border-white/10 dark:hover:bg-white/4"
                              }
                              key={group.id}
                            >
                              <button
                                aria-selected={active}
                                className="flex min-w-0 flex-1 items-center gap-3 text-left text-sm"
                                onClick={() => selectSourceGroup(group.id)}
                                role="tab"
                                type="button"
                              >
                                <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-sky-100 text-xs font-black text-sky-700 dark:bg-sky-400/10 dark:text-sky-200">
                                  {group.label.match(/\d+$/)?.[0] ?? "C"}
                                </span>
                                <span className="min-w-0 flex-1">
                                  <span className="block truncate font-bold text-card-foreground">
                                    {displayLabel}
                                  </span>
                                </span>
                              </button>
                              <button
                                aria-label={selected ? `Remover ${displayLabel}` : `Selecionar ${displayLabel}`}
                                className={
                                  selected
                                    ? "flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground"
                                    : "flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-background text-muted-foreground transition hover:border-primary/40 hover:text-primary dark:border-white/10 dark:bg-white/4"
                                }
                                onClick={() => toggleSourceChat(group.id)}
                                type="button"
                              >
                                {selected ? <Check className="size-4" /> : null}
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="rounded-2xl border border-dashed border-border p-4 text-sm/6 text-muted-foreground">
                        Não foi possível carregar os grupos de origem. Tente novamente mais tarde.
                      </p>
                    )}
                  </div>


                </div>

                <div className="flex min-h-0 flex-col overflow-hidden rounded-3xl border border-border bg-muted/25 dark:border-white/10 dark:bg-white/3">
                  <div className="relative min-h-0 flex-1 overflow-hidden">
                    {sourceGroupsLoading ? (
                      <div className="h-full overflow-y-auto p-5">
                        <MessagePreviewSkeleton />
                      </div>
                    ) : null}
                    {sourceGroupsLoading ? null : sourceGroups.length > 0 ? (
                      sourceGroups
                        .filter((group) => mountedSourceGroupIds.includes(group.id))
                        .map((group) => {
                        const groupMessages = group.messages ?? [];
                        const groupTelegramPostIds = groupMessages
                          .map((sourceMessage) => getTelegramPostId(sourceMessage.post_url))
                          .filter((postId): postId is string => Boolean(postId));
                        const groupWaitingForTelegramPosts =
                          groupTelegramPostIds.length > 0 &&
                          !groupTelegramPostIds.every((postId) =>
                            readyTelegramPostIds.includes(postId)
                          );
                        const active = activeSourceGroup?.id === group.id;

                        return (
                          <div
                            aria-hidden={!active}
                            className={
                              active
                                ? "absolute inset-0 overflow-y-auto p-5 opacity-100 transition-opacity duration-200"
                                : "pointer-events-none absolute inset-0 overflow-y-auto p-5 opacity-0"
                            }
                            key={`preview-${group.id}`}
                          >
                            {groupMessages.length > 0 ? (
                              <div className="relative min-h-full">
                                {active && groupWaitingForTelegramPosts ? (
                                  <MessagePreviewSkeleton count={groupMessages.length} />
                                ) : null}
                                <div
                                  aria-busy={active ? groupWaitingForTelegramPosts : undefined}
                                  className={
                                    active && groupWaitingForTelegramPosts
                                      ? "pointer-events-none absolute inset-x-0 top-0 space-y-3 opacity-0"
                                      : "space-y-3 opacity-100 transition-opacity duration-200"
                                  }
                                >
                                  {groupMessages.map((previewMessage) => {
                                    const telegramPostId = getTelegramPostId(previewMessage.post_url);

                                    if (telegramPostId) {
                                      return (
                                        <div className="max-w-190" key={previewMessage.id}>
                                          <TelegramPostEmbed
                                            onReady={markTelegramPostReady}
                                            postId={telegramPostId}
                                          />
                                        </div>
                                      );
                                    }

                                    const hiddenMessageLinks = getHiddenMessageLinks(previewMessage);

                                    return (
                                      <div
                                        className="relative max-w-190 overflow-hidden rounded-[1.25rem] rounded-tl-md bg-white text-sm/6 text-slate-800 shadow-sm ring-1 ring-sky-900/5 before:absolute before:-left-1.5 before:top-0 before:size-3 before:rounded-br-xl before:bg-white dark:bg-slate-900 dark:text-slate-100 dark:ring-white/10 dark:before:bg-slate-900"
                                        key={previewMessage.id}
                                      >
                                        {previewMessage.image_url ? (
                                          <a
                                            href={previewMessage.post_url ?? previewMessage.image_url}
                                            rel="noreferrer"
                                            target="_blank"
                                          >
                                            <Image
                                              alt=""
                                              className="max-h-90 w-full object-cover"
                                              height={520}
                                              sizes="(min-width: 1024px) 760px, 100vw"
                                              src={previewMessage.image_url}
                                              unoptimized
                                              width={760}
                                            />
                                          </a>
                                        ) : null}
                                        <div className="px-4 py-3">
                                          {previewMessage.text ? (
                                            <p className="whitespace-pre-wrap wrap-break-word">
                                              <LinkedText text={previewMessage.text} />
                                            </p>
                                          ) : null}
                                          {hiddenMessageLinks.length > 0 ? (
                                            <div className="mt-3 flex flex-wrap gap-2">
                                              {hiddenMessageLinks.map((link) => (
                                                <a
                                                  className="rounded-full bg-sky-50 px-3 py-1 text-xs font-semibold text-sky-700 ring-1 ring-sky-100 hover:bg-sky-100 dark:bg-sky-400/10 dark:text-sky-200 dark:ring-sky-400/20"
                                                  href={link.url}
                                                  key={link.url}
                                                  rel="noreferrer"
                                                  target="_blank"
                                                >
                                                  {link.text ?? link.url}
                                                </a>
                                              ))}
                                            </div>
                                          ) : null}
                                          {previewMessage.post_url ? (
                                            <a
                                              className="mt-3 inline-flex text-xs font-semibold text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100"
                                              href={previewMessage.post_url}
                                              rel="noreferrer"
                                              target="_blank"
                                            >
                                              Ver mensagem no Telegram
                                            </a>
                                          ) : null}
                                        </div>
                                      </div>
                                    );
                                  })}
                                </div>
                              </div>
                            ) : (
                              <div className="flex h-full items-center justify-center">
                                <div className="max-w-sm rounded-[1.25rem] bg-white/90 p-4 text-center text-sm/6 text-slate-700 shadow-sm ring-1 ring-sky-900/5 dark:bg-slate-900 dark:text-slate-200 dark:ring-white/10">
                                  As mensagens recentes não estão disponíveis, mas você ainda pode selecionar este grupo.
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <div className="flex h-full items-center justify-center p-5">
                        <div className="max-w-sm rounded-[1.25rem] bg-white/90 p-4 text-center text-sm/6 text-slate-700 shadow-sm ring-1 ring-sky-900/5 dark:bg-slate-900 dark:text-slate-200 dark:ring-white/10">
                          As mensagens recentes não estão disponíveis, mas você ainda pode selecionar este grupo.
                        </div>
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col gap-3 border-t border-border bg-transparent p-4 dark:border-white/10 sm:flex-row sm:items-center sm:justify-between">
                    {message ? (
                      <p
                        className={
                          status === "success"
                            ? "text-sm font-semibold text-primary"
                            : "text-sm font-semibold text-destructive"
                        }
                      >
                        {message}
                      </p>
                    ) : (
                      <p className="text-sm/6 text-muted-foreground">
                        O bot vai publicar as ofertas dos grupos selecionados usando seus links de afiliado.
                      </p>
                    )}
                    <Button
                      className="h-12 shrink-0 gap-2 bg-primary px-6 font-bold text-primary-foreground hover:bg-primary/90"
                      disabled={status === "saving"}
                      onClick={saveSourceGroups}
                      type="button"
                    >
                      {status === "saving" ? <Loader2 className="size-4 animate-spin" /> : null}
                      Salvar grupos de origem
                    </Button>
                  </div>
                </div>
              </div>
            )}
            </div>
            {isCompleting ? (
              <div className="absolute inset-0 z-10 flex items-center justify-center bg-card/95 p-6 text-center backdrop-blur-sm dark:bg-[#0c1414]/95">
                <div className="max-w-md space-y-4">
                  <span className="mx-auto flex size-16 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg shadow-primary/20">
                    <Check className="size-8" />
                  </span>
                  <div>
                    <p className="text-2xl font-black tracking-tight">Tudo pronto!</p>
                    <p className="mt-2 text-sm/6 text-muted-foreground">
                      Seu bot está configurado para copiar as ofertas dos grupos selecionados.
                    </p>
                  </div>
                  <p className="text-xs font-semibold text-primary">Abrindo seu painel…</p>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </>
  );
}
