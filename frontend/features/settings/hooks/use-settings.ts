"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import * as api from "@/features/settings/api/settings-client";
import type { DestinationInput, SettingsData } from "@/features/settings/types";
import type { ConfigSummary, DestinationSummary } from "@/shared/contracts/user-config";
import type { ProviderType } from "@/lib/affiliate-providers";
import { getRequestErrorMessage } from "@/lib/api-error-message";

export function useSettings(initialData: SettingsData) {
  const router = useRouter();
  const [configs, setConfigs] = useState(initialData.configs);
  const [destinations, setDestinations] = useState(initialData.destinations);
  const savedSources = initialData.configs.find((config) => config.config_type === "source_chats")?.config_data?.source_chats;
  const [selectedSources, setSelectedSources] = useState<string[]>(Array.isArray(savedSources) ? savedSources.filter((url): url is string => typeof url === "string" && initialData.sources.some((source) => source.url === url)) : []);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const busyLock = useRef(false);

  async function run(key: string, successMessage: string, operation: () => Promise<void>) {
    if (busyLock.current) return false;
    busyLock.current = true;
    setBusy(key);
    setError("");
    setMessage("");
    try {
      await operation();
      setMessage(successMessage);
      router.refresh();
      return true;
    } catch (cause) {
      setError(getRequestErrorMessage(cause, "Não foi possível salvar a alteração."));
      return false;
    } finally {
      busyLock.current = false;
      setBusy("");
    }
  }

  function replaceConfig(saved: ConfigSummary) {
    setConfigs((current) => [...current.filter((config) => config.id !== saved.id), saved]);
  }

  function saveProvider(type: ProviderType, data: Record<string, string>) {
    return run(type, "Credenciais salvas. As próximas ofertas usarão essa configuração.", async () => {
      const matches = configs.filter((config) => config.config_type === type);
      // Older setups may contain more than one record for the same store.
      if (!matches.length) replaceConfig(await api.saveConfig(type, data));
      for (const existing of matches) {
        replaceConfig(await api.saveConfig(type, { ...existing.config_data, ...data }, existing.id));
      }
    });
  }

  function disconnectProvider(type: ProviderType) {
    return run(type, "Integração removida. As ofertas dessa loja deixarão de ser publicadas.", async () => {
      const matches = configs.filter((config) => config.config_type === type);
      for (const config of matches) {
        await api.deleteConfig(config.id);
        setConfigs((current) => current.filter((item) => item.id !== config.id));
      }
    });
  }

  function saveSources() {
    return run("sources", "Grupos de origem atualizados.", async () => {
      const matches = configs.filter((config) => config.config_type === "source_chats");
      if (!matches.length) replaceConfig(await api.saveConfig("source_chats", { source_chats: selectedSources }));
      for (const existing of matches) {
        replaceConfig(await api.saveConfig("source_chats", { source_chats: selectedSources }, existing.id));
      }
    });
  }

  function saveDestination(data: DestinationInput, id?: number) {
    return run("destinations", "Destino salvo. As permissões do bot foram verificadas quando habilitado.", async () => {
      if (destinations.some((destination) => destination.chat_id === data.chat_id && destination.id !== id)) {
        throw new Error("Esse grupo ou canal já está cadastrado nos seus destinos.");
      }
      const saved = await api.saveDestination(data, id);
      setDestinations((current) => [...current.filter((destination) => destination.id !== saved.id), saved]);
    });
  }

  function toggleDestination(destination: DestinationSummary) {
    return saveDestination({ chat_id: destination.chat_id, title: destination.title ?? null, chat_type: destination.chat_type ?? "group", enabled: !destination.enabled }, destination.id);
  }

  function removeDestination(id: number) {
    return run("destinations", "Destino removido. Novas ofertas não serão enviadas para ele.", async () => {
      await api.deleteDestination(id);
      setDestinations((current) => current.filter((destination) => destination.id !== id));
    });
  }

  return { configs, destinations, selectedSources, setSelectedSources, busy, error, message, saveProvider, disconnectProvider, saveSources, saveDestination, toggleDestination, removeDestination };
}

export type SettingsState = ReturnType<typeof useSettings>;
