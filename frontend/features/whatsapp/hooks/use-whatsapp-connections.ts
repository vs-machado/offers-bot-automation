"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/features/whatsapp/api/whatsapp-client";
import type { WhatsAppConnectionSummary } from "@/features/whatsapp/types";
import { getRequestErrorMessage } from "@/lib/api-error-message";

export function useWhatsAppConnections() {
  const [connections, setConnections] = useState<WhatsAppConnectionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number>();
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);

  const refresh = useCallback(async () => {
    try {
      const rows = await api.getWhatsAppConnections();
      setConnections(rows);
      setSelectedId((current) => rows.some((row) => row.id === current) ? current : rows[0]?.id);
      setError("");
    } catch (cause) {
      setError(getRequestErrorMessage(cause, "Não foi possível carregar conexões."));
    }
  }, []);

  useEffect(() => { const timer = setTimeout(() => void refresh(), 0); return () => clearTimeout(timer); }, [refresh]);

  async function save(name: string, rename = false) {
    if (lock.current) return;
    lock.current = true;
    setIsBusy(true);
    setError("");
    try {
      const row = rename && selectedId !== undefined
        ? await api.renameWhatsAppConnection(selectedId, name)
        : await api.createWhatsAppConnection(name);
      await refresh();
      setSelectedId(row.id);
    } catch (cause) {
      setError(getRequestErrorMessage(cause, "Não foi possível salvar conexão."));
    } finally {
      lock.current = false;
      setIsBusy(false);
    }
  }

  return { connections, selectedId, select: setSelectedId, isBusy, error, refresh, save };
}
