"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/features/whatsapp/api/whatsapp-client";
import type { ManagedWhatsAppChat, WhatsAppGroupDraft, WhatsAppGroupEditor } from "@/features/whatsapp/types";
import type { OfferCategory } from "@/shared/contracts/user-config";
import { getRequestErrorMessage } from "@/lib/api-error-message";

/** Keep saved routing and live chats together; disconnected accounts load saved destinations only. */
export function useWhatsAppManagement(connectionStatus: string, connectionId?: number) {
  const [chats, setChats] = useState<ManagedWhatsAppChat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editor, setEditor] = useState<WhatsAppGroupEditor | null>(null);
  const [updatedAt, setUpdatedAt] = useState("");
  const lock = useRef(false);
  const loadVersion = useRef(0);

  const load = useCallback(async () => {
    const version = ++loadVersion.current;
    setIsLoading(true);
    try {
      const [groups, channels, saved] = await Promise.allSettled([
        connectionStatus === "WORKING" ? api.getManagedWhatsAppGroups(connectionId) : Promise.resolve([]),
        connectionStatus === "WORKING" ? api.getManagedWhatsAppChannels(connectionId) : Promise.resolve([]),
        api.getSavedWhatsAppDestinations(connectionId),
      ]);
      if (version !== loadVersion.current) return;
      const next: ManagedWhatsAppChat[] = [];
      const failures: string[] = [];
      for (const result of [groups, channels]) {
        if (result.status === "fulfilled") next.push(...result.value);
        else failures.push(getRequestErrorMessage(result.reason, "Não foi possível atualizar destinos."));
      }
      if (saved.status === "fulfilled") {
        for (const destination of saved.value) {
          const index = next.findIndex((chat) => chat.id === destination.chat_id);
          if (index >= 0) {
            next[index] = { ...next[index], destination_id: destination.id, enabled: destination.enabled, categories: destination.categories ?? null };
          } else next.push({
            id: destination.chat_id, name: destination.title || destination.chat_id,
            chat_type: destination.chat_type === "channel" ? "channel" : "group",
            member_count: null, capacity: null, capacity_reported: false, is_full: null,
            can_manage: false, destination_id: destination.id, enabled: destination.enabled,
            categories: destination.categories ?? null,
          });
        }
      } else failures.push(getRequestErrorMessage(saved.reason, "Não foi possível carregar destinos salvos."));
      setChats(next);
      setErrors([...new Set(failures)]);
      setUpdatedAt(new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }));
    } finally {
      if (version === loadVersion.current) setIsLoading(false);
    }
  }, [connectionStatus, connectionId]);

  useEffect(() => {
    const version = loadVersion;
    const timer = setTimeout(() => void load(), 0);
    return () => { clearTimeout(timer); version.current++; };
  }, [load]);

  async function run(operation: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true;
    setIsBusy(true);
    setError("");
    setNotice("");
    try { await operation(); }
    catch (cause) { setError(getRequestErrorMessage(cause, "Não foi possível salvar a alteração.")); }
    finally { lock.current = false; setIsBusy(false); }
  }

  function openEditor(chat: ManagedWhatsAppChat | null, mode: "create" | "edit") {
    return run(async () => {
      const details = chat ? await api.getManagedWhatsAppChat(chat, connectionId) : null;
      if (details && !details.can_manage) throw new Error("Sua conta precisa ser administradora para gerenciar este grupo.");
      if (details) setChats((current) => current.map((item) => item.id === details.id ? details : item));
      setEditor({ chat: details, mode, requestId: crypto.randomUUID() });
    });
  }

  function saveGroup(draft: WhatsAppGroupDraft, reusePhoto: boolean) {
    return run(async () => {
      if (!editor) return;
      const result = editor.mode === "edit" && editor.chat
        ? await api.updateWhatsAppGroup(editor.chat, draft, connectionId)
        : await api.createWhatsAppGroup({ ...draft, source_id: editor.chat?.id ?? null, reuse_photo: reusePhoto, request_id: editor.requestId }, connectionId);
      setEditor(null);
      setNotice(result.warnings.length
        ? `${result.name}: ${result.warnings.join(" ")} Publicações desativadas até concluir configuração.`
        : `${result.name}: ${editor.mode === "create" ? "grupo criado" : "alterações salvas"}.`);
      await load();
    });
  }

  function saveRouting(chat: ManagedWhatsAppChat, categories: OfferCategory[] | null, enabled: boolean) {
    return run(async () => {
      const result = await api.saveWhatsAppRouting(chat, categories, enabled, connectionId);
      setChats((current) => current.map((item) => item.id === chat.id ? { ...item, ...result } : item));
      setNotice(`${chat.name}: categorias e publicação atualizadas.`);
    });
  }

  function refreshChat(chat: ManagedWhatsAppChat) {
    return run(async () => {
      const result = await api.getManagedWhatsAppChat(chat, connectionId);
      setChats((current) => current.map((item) => item.id === chat.id ? result : item));
    });
  }

  function removeDestination(chat: ManagedWhatsAppChat) {
    return run(async () => {
      if (chat.destination_id == null) return;
      await api.removeWhatsAppDestination(chat.destination_id);
      setNotice(`${chat.name}: destino removido. O grupo ou canal continua no WhatsApp.`);
      await load();
    });
  }

  function moveDestination(chat: ManagedWhatsAppChat, targetId: number) {
    return run(async () => {
      await api.moveWhatsAppDestination(chat, targetId);
      setNotice(`${chat.name}: transferido com publicações desativadas. Selecione nova conexão e ative após conferir permissões.`);
      await load();
    });
  }

  return { chats, isLoading, isBusy, errors, error, notice, editor, updatedAt,
    refresh: () => run(load), openEditor, closeEditor: () => setEditor(null), saveGroup, saveRouting, refreshChat, removeDestination, moveDestination };
}
