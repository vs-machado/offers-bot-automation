"use client";

import { useEffect, useState } from "react";
import type { DestinationSummary } from "@/shared/contracts/user-config";
import { getGamingSettings, saveGamingPolicy } from "../api/gaming-policy-client";
import type { GamingPolicy } from "../types";

export function useGamingPolicy() {
  const [policy, setPolicy] = useState<GamingPolicy>({ platforms: {}, destinations: {} });
  const [destinations, setDestinations] = useState<DestinationSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getGamingSettings(controller.signal).then(([loaded, owned]) => {
      if (controller.signal.aborted) return;
      // Remove obsolete overrides for destinations deleted since the last save.
      const ids = new Set(owned.map((destination) => destination.chat_id));
      setPolicy({ ...loaded, destinations: Object.fromEntries(Object.entries(loaded.destinations).filter(([id]) => ids.has(id))) });
      setDestinations(owned);
      setError("");
    }).catch((cause: unknown) => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Não foi possível carregar o filtro gamer.");
    }).finally(() => {
      if (!controller.signal.aborted) setIsLoading(false);
    });
    return () => controller.abort();
  }, [loadAttempt]);

  async function save() {
    setIsSaving(true);
    setError("");
    setMessage("");
    try {
      setPolicy(await saveGamingPolicy(policy));
      setMessage("Filtro gamer salvo. As novas regras valem também para ofertas aguardando envio.");
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "Não foi possível salvar o filtro gamer.");
    } finally {
      setIsSaving(false);
    }
  }

  function retry() {
    setIsLoading(true);
    setLoadAttempt((value) => value + 1);
  }

  return { policy, setPolicy, destinations, isLoading, isSaving, error, message, save, retry };
}
