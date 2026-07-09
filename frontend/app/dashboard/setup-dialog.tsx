"use client";

import { ArrowLeft, ArrowRight, Check, Copy, KeyRound, Loader2, Send, X } from "lucide-react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { FormEvent, Fragment, useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";

const platformBotUsername = "tgtestoffersbot";
const telegramEmbedScale = 0.86;

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

type SourceGroup = {
  id: string;
  label: string;
  messages?: SourceMessage[];
};

type SourceMessage = {
  id: number;
  text: string;
  image_url?: string;
  post_url?: string;
  links?: Array<{
    text?: string;
    url: string;
  }>;
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

function getProviderData(
  provider: Provider,
  configs: ConfigSummary[]
): Record<string, string> {
  const existingConfig = getExistingConfig(configs, provider.type);
  return provider.fields.reduce<Record<string, string>>((data, field) => {
    const value = existingConfig?.config_data?.[field.key];
    data[field.key] = typeof value === "string" ? value : "";
    return data;
  }, {});
}

function getSavedSourceChats(configs: ConfigSummary[]) {
  const sourceConfig = configs.find((config) => config.config_type === "source_chats");
  const sourceChats = sourceConfig?.config_data?.source_chats;
  return Array.isArray(sourceChats)
    ? sourceChats.filter((chat): chat is string => typeof chat === "string")
    : [];
}

function getSourceDisplayLabel(group: SourceGroup) {
  const sourceOption = group.label.match(/^Source option (\d+)$/);
  if (sourceOption?.[1]) {
    return `Group ${sourceOption[1]}`;
  }

  const customSource = group.label.match(/^Custom source (\d+)$/);
  if (customSource?.[1]) {
    return `Custom group ${customSource[1]}`;
  }

  return group.label;
}

function renderLinkedText(text: string) {
  return text.split(/(https?:\/\/[^\s]+)/g).map((part, index) => {
    if (!part) {
      return null;
    }

    if (part.startsWith("http://") || part.startsWith("https://")) {
      const trailingMatch = part.match(/[),.;:!?]+$/);
      const trailing = trailingMatch?.[0] ?? "";
      const url = trailing ? part.slice(0, -trailing.length) : part;

      return (
        <Fragment key={`${part}-${index}`}>
          <a
            className="break-all font-semibold text-sky-700 underline decoration-sky-300 underline-offset-2 hover:text-sky-900 dark:text-sky-300 dark:decoration-sky-500/70 dark:hover:text-sky-100"
            href={url}
            rel="noreferrer"
            target="_blank"
          >
            {url}
          </a>
          {trailing}
        </Fragment>
      );
    }

    return part.split("\n").map((line, lineIndex) => (
      <Fragment key={`${part}-${index}-${lineIndex}`}>
        {lineIndex > 0 ? <br /> : null}
        {line}
      </Fragment>
    ));
  });
}

function getHiddenMessageLinks(message: SourceMessage) {
  return (message.links ?? []).filter(
    (link) => link.url && !message.text.includes(link.url)
  );
}

function getTelegramPostId(postUrl?: string) {
  if (!postUrl) {
    return null;
  }

  try {
    const url = new URL(postUrl);
    if (!["t.me", "telegram.me"].includes(url.hostname.toLowerCase())) {
      return null;
    }

    const parts = url.pathname.split("/").filter(Boolean);
    if (parts.length < 2) {
      return null;
    }

    return `${parts[parts.length - 2]}/${parts[parts.length - 1]}`;
  } catch {
    return null;
  }
}

function TelegramPostEmbed({
  onReady,
  postId,
}: {
  onReady: (postId: string) => void;
  postId: string;
}) {
  const [scaledHeight, setScaledHeight] = useState<number>();
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    container.innerHTML = "";
    let ready = false;
    let readinessStarted = false;
    let pollTimer: number | undefined;
    let resizeObserver: ResizeObserver | undefined;
    const startedAt = Date.now();

    const markReady = () => {
      if (ready) {
        return;
      }
      ready = true;
      onReady(postId);
    };

    const startReadinessCheck = () => {
      if (readinessStarted) {
        return;
      }
      const iframe = container.querySelector("iframe");
      if (!iframe) {
        return;
      }

      const syncScaledHeight = () => {
        const height = Math.round(iframe.offsetHeight || iframe.getBoundingClientRect().height);
        if (height > 0) {
          setScaledHeight(Math.ceil(height * telegramEmbedScale) + 2);
        }
        return height;
      };

      readinessStarted = true;
      resizeObserver = typeof ResizeObserver === "undefined"
        ? undefined
        : new ResizeObserver(syncScaledHeight);
      resizeObserver?.observe(iframe);

      let lastHeight = syncScaledHeight();
      let stableSince = Date.now();

      pollTimer = window.setInterval(() => {
        const height = syncScaledHeight();
        if (Math.abs(height - lastHeight) > 2) {
          lastHeight = height;
          stableSince = Date.now();
        }

        const oldEnough = Date.now() - startedAt > 3600;
        const stableEnough = Date.now() - stableSince > 700;
        if (height > 80 && oldEnough && stableEnough) {
          markReady();
        }
      }, 150);
    };

    const observer = new MutationObserver(() => {
      const iframe = container.querySelector("iframe");
      if (iframe) {
        iframe.addEventListener("load", startReadinessCheck, { once: true });
        startReadinessCheck();
      }
    });
    observer.observe(container, { childList: true, subtree: true });

    const script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?24";
    script.dataset.telegramPost = postId;
    script.dataset.width = "100%";
    script.dataset.dark = document.documentElement.classList.contains("dark") ? "1" : "0";
    container.appendChild(script);
    const fallbackTimer = window.setTimeout(markReady, 7000);

    return () => {
      window.clearTimeout(fallbackTimer);
      if (pollTimer) {
        window.clearInterval(pollTimer);
      }
      resizeObserver?.disconnect();
      observer.disconnect();
      container.innerHTML = "";
    };
  }, [onReady, postId]);

  return (
    <div
      className="overflow-hidden"
      style={scaledHeight ? { height: scaledHeight } : undefined}
    >
      <div
        className="origin-top-left [&_.telegram-post]:mx-0 [&_.telegram-post]:my-0 [&_iframe]:mx-0 [&_iframe]:my-0"
        ref={containerRef}
        style={{
          transform: `scale(${telegramEmbedScale})`,
          width: `${100 / telegramEmbedScale}%`,
        }}
      />
    </div>
  );
}

function SourceGroupsSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 7 }).map((_, index) => (
        <div className="flex items-center gap-3 rounded-2xl p-2" key={index}>
          <div className="size-10 shrink-0 animate-pulse rounded-full bg-muted dark:bg-white/10" />
          <div className="h-4 w-24 animate-pulse rounded-full bg-muted dark:bg-white/10" />
          <div className="ml-auto size-8 shrink-0 animate-pulse rounded-full bg-muted dark:bg-white/10" />
        </div>
      ))}
    </div>
  );
}

function MessagePreviewSkeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, index) => (
        <div className="mx-auto flex w-full max-w-[560px] items-start gap-2" key={index}>
          <div className="mt-3 size-9 shrink-0 animate-pulse rounded-full bg-muted dark:bg-white/10" />
          <div className="min-w-0 flex-1 overflow-hidden rounded-[1rem] border border-border bg-background shadow-sm dark:border-white/10 dark:bg-[#111d2a]">
            <div className="flex items-center gap-2 px-3 pt-3">
              <div className="h-3.5 w-24 animate-pulse rounded-full bg-sky-200 dark:bg-sky-400/25" />
              <div className="ml-auto size-5 shrink-0 animate-pulse rounded-full bg-sky-200 dark:bg-sky-400/25" />
            </div>
            <div className="space-y-3 px-3 py-3">
              <div className="space-y-2.5">
                <div className="h-3.5 w-11/12 animate-pulse rounded-full bg-muted dark:bg-white/10" />
                <div className="h-3.5 w-3/4 animate-pulse rounded-full bg-muted dark:bg-white/10" />
                <div className="h-3.5 w-5/6 animate-pulse rounded-full bg-muted dark:bg-white/10" />
              </div>
              {index % 2 === 1 ? (
                <div className="flex gap-3 rounded-lg border-l-2 border-sky-300 bg-muted/60 p-2 dark:border-sky-500/50 dark:bg-white/5">
                  <div className="min-w-0 flex-1 space-y-2">
                    <div className="h-3 w-16 animate-pulse rounded-full bg-sky-200 dark:bg-sky-400/25" />
                    <div className="h-3 w-11/12 animate-pulse rounded-full bg-muted-foreground/20 dark:bg-white/10" />
                    <div className="h-3 w-2/3 animate-pulse rounded-full bg-muted-foreground/20 dark:bg-white/10" />
                  </div>
                  <div className="size-14 shrink-0 animate-pulse rounded-md bg-muted dark:bg-white/10" />
                </div>
              ) : null}
              <div className="flex items-center gap-2">
                <div className="h-3 w-20 animate-pulse rounded-full bg-sky-200 dark:bg-sky-400/25" />
                <div className="ml-auto h-3 w-28 animate-pulse rounded-full bg-muted dark:bg-white/10" />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function SetupDialog({ hasEnabledDestination, destinations, configs }: SetupDialogProps) {
  const router = useRouter();
  const enabledDestination = destinations.find((destination) => destination.enabled);
  const [open, setOpen] = useState(false);
  const [screen, setScreen] = useState<"destination" | "providers" | "sources">(
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
  const [sourceGroups, setSourceGroups] = useState<SourceGroup[]>([]);
  const [sourceGroupsLoaded, setSourceGroupsLoaded] = useState(false);
  const [selectedSourceChats, setSelectedSourceChats] = useState<string[]>(
    getSavedSourceChats(configs)
  );
  const [activeSourceId, setActiveSourceId] = useState<string | null>(null);
  const [mountedSourceGroupIds, setMountedSourceGroupIds] = useState<string[]>([]);
  const [readyTelegramPostIds, setReadyTelegramPostIds] = useState<string[]>([]);
  const [customSourceChat, setCustomSourceChat] = useState("");
  const [customSourcePreviewLoading, setCustomSourcePreviewLoading] = useState(false);
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
  const canSaveSources = selectedSourceChats.length > 0;
  const sourceGroupsLoading = open && !sourceGroupsLoaded && sourceGroups.length === 0;
  const activeSourceGroup =
    (activeSourceId ? sourceGroups.find((group) => group.id === activeSourceId) : undefined) ??
    sourceGroups[0];
  const activeTelegramPostIds = (activeSourceGroup?.messages ?? [])
    .map((sourceMessage) => getTelegramPostId(sourceMessage.post_url))
    .filter((postId): postId is string => Boolean(postId));
  const activeTelegramPostsReady = activeTelegramPostIds.every((postId) =>
    readyTelegramPostIds.includes(postId)
  );
  const headerLabel =
    screen === "destination"
      ? "Telegram bot setup"
      : screen === "providers"
        ? "Affiliate provider setup"
        : "Source group setup";
  const headerTitle =
    screen === "destination"
      ? "Connect your destination"
      : screen === "providers"
        ? "Connect affiliate providers"
        : "Choose source groups";
  const headerDescription =
    screen === "destination"
      ? "Add the platform Telegram bot to your destination, then save the destination chat ID."
      : screen === "providers"
        ? "Save credentials for at least one provider so the bot can convert product links into your affiliate links."
        : "Review recent messages from built-in source groups, then select which ones should be copied.";

  useEffect(() => {
    if (!open || sourceGroupsLoaded || sourceGroups.length > 0) {
      return;
    }

    let cancelled = false;

    async function loadSourceGroups() {
      try {
        const response = await fetch("/api/backend/users/me/source-groups/messages");
        if (!response.ok) {
          return;
        }

        const data = (await response.json()) as { groups?: SourceGroup[] };
        if (!cancelled) {
          const groups = data.groups ?? [];
          setSourceGroups(groups);
          setActiveSourceId((current) => current ?? groups[0]?.id ?? null);
          setMountedSourceGroupIds((current) =>
            current.length > 0 || !groups[0] ? current : [groups[0].id]
          );
        }
      } catch {
        if (!cancelled) {
          setSourceGroups([]);
        }
      } finally {
        if (!cancelled) {
          setSourceGroupsLoaded(true);
        }
      }
    }

    void loadSourceGroups();

    return () => {
      cancelled = true;
    };
  }, [open, sourceGroups.length, sourceGroupsLoaded]);

  useEffect(() => {
    if (
      !open ||
      screen !== "sources" ||
      !activeSourceGroup ||
      !activeTelegramPostsReady ||
      sourceGroups.every((group) => mountedSourceGroupIds.includes(group.id))
    ) {
      return;
    }

    const idleWindow = window as Window & {
      requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    let idleId: number | undefined;
    const delayId = window.setTimeout(() => {
      const mountNextGroup = () => {
        setMountedSourceGroupIds((current) => {
          const nextGroup = sourceGroups.find((group) => !current.includes(group.id));
          return nextGroup ? [...current, nextGroup.id] : current;
        });
      };

      if (idleWindow.requestIdleCallback) {
        idleId = idleWindow.requestIdleCallback(mountNextGroup, { timeout: 2500 });
        return;
      }

      mountNextGroup();
    }, 700);

    return () => {
      window.clearTimeout(delayId);
      if (idleId !== undefined) {
        idleWindow.cancelIdleCallback?.(idleId);
      }
    };
  }, [
    activeSourceGroup,
    activeTelegramPostsReady,
    mountedSourceGroupIds,
    open,
    screen,
    sourceGroups,
  ]);

  const markTelegramPostReady = useCallback((postId: string) => {
    setReadyTelegramPostIds((current) =>
      current.includes(postId) ? current : [...current, postId]
    );
  }, []);

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
    setScreen(screen === "sources" ? "providers" : "destination");
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

  function goToSources() {
    if (!canFinish) {
      setStatus("error");
      setMessage("Connect at least one affiliate provider before choosing source groups.");
      return;
    }

    setScreen("sources");
    setStatus("idle");
    setMessage("");
  }

  function toggleSourceChat(chat: string) {
    setSelectedSourceChats((current) =>
      current.includes(chat)
        ? current.filter((item) => item !== chat)
        : [...current, chat]
    );
  }

  function selectSourceGroup(groupId: string) {
    setMountedSourceGroupIds((current) =>
      current.includes(groupId) ? current : [...current, groupId]
    );
    setActiveSourceId(groupId);
  }

  async function addCustomSourceChat() {
    const trimmedChat = customSourceChat.trim();
    if (!trimmedChat) {
      return;
    }

    setSelectedSourceChats((current) =>
      current.includes(trimmedChat) ? current : [...current, trimmedChat]
    );
    selectSourceGroup(trimmedChat);
    setCustomSourceChat("");

    if (sourceGroups.some((group) => group.id === trimmedChat)) {
      return;
    }

    setCustomSourcePreviewLoading(true);

    try {
      const response = await fetch("/api/backend/users/me/source-groups/preview", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ chat: trimmedChat }),
      });
      const data = response.ok
        ? ((await response.json()) as { groups?: SourceGroup[] })
        : null;
      const customGroup = data?.groups?.[0] ?? {
        id: trimmedChat,
        label: "Custom source",
        messages: [],
      };

      setSourceGroups((current) =>
        current.some((group) => group.id === trimmedChat)
          ? current
          : [
              ...current,
              {
                ...customGroup,
                id: trimmedChat,
                label: `Custom source ${
                  current.filter((group) => group.label.startsWith("Custom source"))
                    .length + 1
                }`,
              },
            ]
      );
    } catch {
      setSourceGroups((current) =>
        current.some((group) => group.id === trimmedChat)
          ? current
          : [
              ...current,
              {
                id: trimmedChat,
                label: `Custom source ${
                  current.filter((group) => group.label.startsWith("Custom source"))
                    .length + 1
                }`,
                messages: [],
              },
            ]
      );
    } finally {
      setCustomSourcePreviewLoading(false);
    }
  }

  async function saveSourceGroups() {
    if (!canSaveSources) {
      setStatus("error");
      setMessage("Select or add at least one source group.");
      return;
    }

    setStatus("saving");
    setMessage("");

    const existingConfig = savedConfigs.find((config) => config.config_type === "source_chats");

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
            config_type: "source_chats",
            config_data: {
              source_chats: selectedSourceChats,
            },
          }),
        }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const detail = data?.detail;
        throw new Error(typeof detail === "string" ? detail : "Could not save source groups.");
      }

      const savedConfig = (await response.json()) as ConfigSummary;
      setSavedConfigs((current) => [
        ...current.filter((config) => config.config_type !== "source_chats"),
        savedConfig,
      ]);
      setStatus("success");
      setMessage("Source groups saved. Offers from selected groups will be copied.");
      closeDialog();
      router.refresh();
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Could not save source groups.");
    }
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

    goToSources();
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
          <div className="flex h-[min(94dvh,880px)] w-full max-w-6xl flex-col overflow-hidden rounded-[2rem] border border-border bg-card text-card-foreground shadow-[0_30px_120px_rgba(15,23,42,0.35)] dark:border-white/10 dark:bg-[#0c1414]">
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
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
                    {headerDescription}
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

            <div className={screen === "sources" ? "flex-1 overflow-hidden p-5 pt-0" : "flex-1 overflow-y-auto p-5 pt-0"}>
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
            ) : screen === "providers" ? (
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
                        ? "At least one provider is connected. Continue to choose which source groups the bot should copy."
                        : "Connect at least one provider before finishing setup."}
                    </p>
                    <Button
                      className="h-12 gap-2 bg-primary px-6 font-bold text-primary-foreground hover:bg-primary/90"
                      onClick={finishProviderSetup}
                      type="button"
                    >
                      Continue to sources <ArrowRight className="size-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="setup-screen-slide mt-6 grid h-[calc(100%-1.5rem)] min-h-0 gap-4 lg:grid-cols-[300px_minmax(0,1fr)]" key="sources-screen">
                <div className="flex min-h-0 flex-col overflow-hidden rounded-3xl border border-border bg-muted/25 dark:border-white/10 dark:bg-white/[0.03]">
                  <div className="border-b border-border p-4 dark:border-white/10">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-bold">Sources</p>
                      <span className="rounded-full bg-primary/10 px-3 py-1 text-xs font-bold text-primary">
                        {selectedSourceChats.length} selected
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-muted-foreground">
                      Pick a source, read recent messages, then add it to copying.
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

                          return (
                            <div
                              className={
                                active
                                  ? "flex items-center gap-2 rounded-2xl border border-primary/30 bg-primary/10 p-2 transition"
                                  : "flex items-center gap-2 rounded-2xl border border-transparent p-2 transition hover:border-border hover:bg-background/70 dark:hover:border-white/10 dark:hover:bg-white/[0.04]"
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
                                    {getSourceDisplayLabel(group)}
                                  </span>
                                </span>
                              </button>
                              <button
                                aria-label={selected ? `Remove ${getSourceDisplayLabel(group)}` : `Select ${getSourceDisplayLabel(group)}`}
                                className={
                                  selected
                                    ? "flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground"
                                    : "flex size-8 shrink-0 items-center justify-center rounded-full border border-border bg-background text-muted-foreground transition hover:border-primary/40 hover:text-primary dark:border-white/10 dark:bg-white/[0.04]"
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
                      <p className="rounded-2xl border border-dashed border-border p-4 text-sm leading-6 text-muted-foreground">
                        Source previews unavailable. Paste a group URL or ID below.
                      </p>
                    )}
                  </div>

                  <div className="border-t border-border p-3 dark:border-white/10">
                    <label className="block space-y-2">
                      <span className="text-xs font-bold text-card-foreground">
                        Add custom group URL or ID
                      </span>
                      <input
                        className="h-11 w-full rounded-2xl border border-border bg-background px-3 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary focus:ring-4 focus:ring-primary/10 dark:border-white/10 dark:bg-white/[0.04]"
                        onChange={(event) => setCustomSourceChat(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            void addCustomSourceChat();
                          }
                        }}
                        placeholder="https://t.me/sourceurl"
                        value={customSourceChat}
                      />
                    </label>
                    <Button
                      className="mt-3 h-10 w-full gap-2"
                      disabled={customSourcePreviewLoading}
                      onClick={() => void addCustomSourceChat()}
                      type="button"
                      variant="outline"
                    >
                      {customSourcePreviewLoading ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : null}
                      Add source
                    </Button>
                  </div>
                </div>

                <div className="flex min-h-0 flex-col overflow-hidden rounded-3xl border border-border bg-muted/25 dark:border-white/10 dark:bg-white/[0.03]">
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
                                        <div className="max-w-[760px]" key={previewMessage.id}>
                                          <TelegramPostEmbed
                                            onReady={markTelegramPostReady}
                                            postId={telegramPostId}
                                          />
                                        </div>
                                      );
                                    }

                                    return (
                                      <div
                                        className="relative max-w-[760px] overflow-hidden rounded-[1.25rem] rounded-tl-md bg-white text-sm leading-6 text-slate-800 shadow-sm ring-1 ring-sky-900/5 before:absolute before:left-[-6px] before:top-0 before:size-3 before:rounded-br-xl before:bg-white dark:bg-slate-900 dark:text-slate-100 dark:ring-white/10 dark:before:bg-slate-900"
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
                                              className="max-h-[360px] w-full object-cover"
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
                                            <p className="whitespace-pre-wrap break-words">
                                              {renderLinkedText(previewMessage.text)}
                                            </p>
                                          ) : null}
                                          {getHiddenMessageLinks(previewMessage).length > 0 ? (
                                            <div className="mt-3 flex flex-wrap gap-2">
                                              {getHiddenMessageLinks(previewMessage).map((link) => (
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
                                              Open original message
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
                                <div className="max-w-sm rounded-[1.25rem] bg-white/90 p-4 text-center text-sm leading-6 text-slate-700 shadow-sm ring-1 ring-sky-900/5 dark:bg-slate-900 dark:text-slate-200 dark:ring-white/10">
                                  Recent messages unavailable. You can still select this source.
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })
                    ) : (
                      <div className="flex h-full items-center justify-center p-5">
                        <div className="max-w-sm rounded-[1.25rem] bg-white/90 p-4 text-center text-sm leading-6 text-slate-700 shadow-sm ring-1 ring-sky-900/5 dark:bg-slate-900 dark:text-slate-200 dark:ring-white/10">
                          Recent messages unavailable. You can still select this source.
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
                      <p className="text-sm leading-6 text-muted-foreground">
                        Selected sources will be copied into your destination after provider conversion.
                      </p>
                    )}
                    <Button
                      className="h-12 shrink-0 gap-2 bg-primary px-6 font-bold text-primary-foreground hover:bg-primary/90"
                      disabled={status === "saving"}
                      onClick={saveSourceGroups}
                      type="button"
                    >
                      {status === "saving" ? <Loader2 className="size-4 animate-spin" /> : null}
                      Save source groups
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
