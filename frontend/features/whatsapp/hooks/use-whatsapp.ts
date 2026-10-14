"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/features/whatsapp/api/whatsapp-client";
import type { WhatsAppChat, WhatsAppStatus } from "@/features/whatsapp/types";
import { getRequestErrorMessage } from "@/lib/api-error-message";

export function useWhatsApp() {
  const [connection, setConnection] = useState<WhatsAppStatus>({ status: "LOADING", name: null });
  const [qr, setQr] = useState("");
  const [groups, setGroups] = useState<WhatsAppChat[]>([]);
  const [channels, setChannels] = useState<WhatsAppChat[]>([]);
  const [channelsError, setChannelsError] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const lock = useRef(false);
  const lastStatus = useRef("");

  const fetchChats = useCallback(async () => {
    const [groupResult, channelResult] = await Promise.allSettled([api.getWhatsAppGroups(), api.getWhatsAppChannels()]);
    if (groupResult.status === "rejected") throw groupResult.reason;
    setGroups(groupResult.value);
    if (channelResult.status === "fulfilled") {
      setChannels(channelResult.value);
      setChannelsError("");
    } else {
      setChannels([]);
      setChannelsError("Canais indisponíveis nesta conexão. Grupos continuam disponíveis; tente atualizar destinos.");
    }
  }, []);

  const refresh = useCallback(async () => {
    if (lock.current) return;
    lock.current = true;
    try {
      const status = await api.getWhatsAppStatus();
      setConnection(status);
      if (status.status === "SCAN_QR_CODE") {
        setQr((await api.getWhatsAppQr()).qr);
      } else {
        setQr("");
      }
      if (status.status === "WORKING" && lastStatus.current !== "WORKING") {
        await fetchChats();
      } else if (status.status !== "WORKING") {
        setGroups([]);
        setChannels([]);
      }
      lastStatus.current = status.status;
      setError("");
    } catch (cause) {
      setError(getRequestErrorMessage(cause, "Não foi possível consultar o WhatsApp."));
    } finally {
      lock.current = false;
    }
  }, [fetchChats]);

  useEffect(() => {
    const initial = setTimeout(() => void refresh(), 0);
    const timer = setInterval(() => void refresh(), 5000);
    return () => { clearTimeout(initial); clearInterval(timer); };
  }, [refresh]);

  async function run(operation: () => Promise<void>) {
    if (lock.current) return false;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      await operation();
      return true;
    } catch (cause) {
      setError(getRequestErrorMessage(cause, "Não foi possível atualizar o WhatsApp."));
      return false;
    } finally {
      lock.current = false;
      setBusy(false);
    }
  }

  function start() {
    return run(async () => {
      setConnection(await api.startWhatsApp());
      lastStatus.current = "";
    });
  }

  function disconnect() {
    return run(async () => {
      await api.disconnectWhatsApp();
      setConnection({ status: "STOPPED", name: null });
      setQr("");
      setGroups([]);
      setChannels([]);
      lastStatus.current = "";
    });
  }

  function loadGroups() {
    return run(fetchChats);
  }

  return { connection, qr, groups, channels, channelsError, busy, error, start, disconnect, loadGroups };
}
