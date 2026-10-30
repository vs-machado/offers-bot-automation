"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/features/whatsapp/api/whatsapp-client";
import type { WhatsAppPolicy, WhatsAppPolicyData } from "@/features/whatsapp/types";
import { getRequestErrorMessage } from "@/lib/api-error-message";

export function useWhatsAppPolicy(connectionId?: number) {
  const [data, setData] = useState<WhatsAppPolicyData | null>(null);
  const [draft, setDraft] = useState<WhatsAppPolicy | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [isBusy, setIsBusy] = useState(false);
  const lock = useRef(false);

  const refresh = useCallback(async () => {
    if (lock.current) return;
    lock.current = true;
    try {
      const result = await api.getWhatsAppPolicy(connectionId);
      setData(result);
      setDraft((current) => current ?? result.settings);
      setError("");
    } catch (cause) {
      setError(getRequestErrorMessage(cause, "Não foi possível consultar os limites de publicação."));
    } finally {
      lock.current = false;
    }
  }, [connectionId]);

  useEffect(() => {
    const initial = setTimeout(() => void refresh(), 0);
    const timer = setInterval(() => void refresh(), 30000);
    return () => { clearTimeout(initial); clearInterval(timer); };
  }, [refresh]);

  async function run(operation: () => Promise<void>, success: string) {
    if (lock.current) return;
    lock.current = true;
    setIsBusy(true);
    setMessage("");
    setError("");
    try {
      await operation();
      setData(await api.getWhatsAppPolicy(connectionId));
      setMessage(success);
    } catch (cause) {
      setError(getRequestErrorMessage(cause, "Não foi possível atualizar os controles de publicação."));
    } finally {
      lock.current = false;
      setIsBusy(false);
    }
  }

  function save() {
    if (!draft) return;
    if (draft.ttl_seconds < Math.max(draft.burst_window_seconds, draft.collection_seconds) + 30) {
      setError("A validade deve superar as janelas de coleta e rajada em pelo menos 30 segundos.");
      return;
    }
    if (draft.start_hour_utc >= draft.end_hour_utc) {
      setError("O início deve ser anterior ao fim da janela de publicação.");
      return;
    }
    if (draft.max_per_day < draft.max_per_hour) {
      setError("O limite diário deve ser maior ou igual ao horário.");
      return;
    }
    return run(async () => { setDraft(await api.saveWhatsAppPolicy(draft, connectionId)); }, "Limites salvos. A fila usará as novas regras sem renovar a validade das ofertas.");
  }

  function resume() {
    return run(() => api.resumeWhatsAppDeliveries(connectionId), "Pausas removidas. Destinos desativados e ofertas descartadas não serão reativados.");
  }

  function change(key: keyof WhatsAppPolicy, value: number | string | null) {
    setDraft((current) => current ? { ...current, [key]: value } : current);
    setMessage("");
  }

  return { data, draft, error, message, isBusy, refresh, change, save, resume };
}
