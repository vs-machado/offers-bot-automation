import { useCallback, useEffect, useState } from "react";
import { getWebsite, saveWebsite, recoverWebsite } from "@/features/whatsapp/api/website-client";
import { getSavedWhatsAppDestinations } from "@/features/whatsapp/api/whatsapp-client";
import type { WebsiteData, WebsiteSettings } from "@/features/whatsapp/website-types";
import type { DestinationSummary } from "@/shared/contracts/user-config";

export function useWhatsAppWebsite() {
  const [data, setData] = useState<WebsiteData | null>(null);
  const [draft, setDraft] = useState<WebsiteSettings | null>(null);
  const [destinations, setDestinations] = useState<DestinationSummary[]>([]);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const refresh = useCallback(async () => {
    setIsBusy(true);
    setError("");
    try {
      const [next, groups] = await Promise.all([getWebsite(), getSavedWhatsAppDestinations()]);
      setData(next);
      setDraft(next.settings);
      setDestinations(groups.filter((group) => group.chat_type === "group"));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível carregar o site.");
    } finally { setIsBusy(false); }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void refresh(), 0);
    return () => clearTimeout(timer);
  }, [refresh]);

  function change<K extends keyof WebsiteSettings>(key: K, value: WebsiteSettings[K]) {
    setDraft((previous) => previous ? { ...previous, [key]: value, ...(key === "connection_id" ? { template_destination_id: null } : {}) } : previous);
  }

  async function save(recoveryId?: number) {
    if (!draft) return;
    setIsBusy(true);
    setError("");
    setMessage("");
    try {
      const next = recoveryId === undefined ? await saveWebsite(draft) : await recoverWebsite(recoveryId);
      setData(next);
      setDraft(next.settings);
      setMessage("Configuração salva. Monitor verifica o site em instantes; use Atualizar estado para acompanhar.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível salvar o site.");
    } finally { setIsBusy(false); }
  }

  return { data, draft, destinations, isBusy, error, message, change, save, refresh };
}
