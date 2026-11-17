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
  const [entryUrl, setEntryUrl] = useState("");

  const refresh = useCallback(async () => {
    setIsBusy(true);
    setError("");
    try {
      const [next, groups] = await Promise.all([getWebsite(), getSavedWhatsAppDestinations()]);
      setData(next);
      setEntryUrl(next.entry_path ? new URL(next.entry_path, window.location.origin).href : "");
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

  function selectTemplate(templateDestinationId: number | null) {
    setDraft((previous) => {
      if (!previous) return previous;
      const template = destinations.find((group) => group.id === templateDestinationId);
      const name = template ? (template.title?.trim() || template.chat_id).slice(0, 90) : previous.group_name;
      return { ...previous, template_destination_id: templateDestinationId, group_name: name };
    });
  }

  async function save(recoveryId?: number) {
    if (!draft) return;
    setIsBusy(true);
    setError("");
    setMessage("");
    try {
      const next = recoveryId === undefined ? await saveWebsite(draft) : await recoverWebsite(recoveryId);
      setData(next);
      setEntryUrl(next.entry_path ? new URL(next.entry_path, window.location.origin).href : "");
      setDraft(next.settings);
      setMessage("Configuração salva. Configure o link público no site uma vez; o monitor atualiza o grupo em instantes.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Não foi possível salvar o site.");
    } finally { setIsBusy(false); }
  }

  return { data, draft, destinations, isBusy, error, message, entryUrl, change, selectTemplate, save, refresh };
}
