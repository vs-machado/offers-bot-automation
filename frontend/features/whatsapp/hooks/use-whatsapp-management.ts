"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import * as api from "@/features/whatsapp/api/whatsapp-client";
import type { ManagedWhatsAppChat, WhatsAppGroupDraft, WhatsAppGroupEditor } from "@/features/whatsapp/types";
import type { OfferCategory } from "@/shared/contracts/user-config";
import { getRequestErrorMessage } from "@/lib/api-error-message";

export function useWhatsAppManagement() {
  const [chats, setChats] = useState<ManagedWhatsAppChat[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isBusy, setIsBusy] = useState(false);
  const [errors, setErrors] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [editor, setEditor] = useState<WhatsAppGroupEditor | null>(null);
  const [updatedAt, setUpdatedAt] = useState("");
  const lock = useRef(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const [groups, channels, saved] = await Promise.allSettled([
        api.getManagedWhatsAppGroups(), api.getManagedWhatsAppChannels(), api.getSavedWhatsAppDestinations(),
      ]);
      const next: ManagedWhatsAppChat[] = [];
      const failures: string[] = [];
      for (const result of [groups, channels]) {
        if (result.status === "fulfilled") next.push(...result.value);
        else failures.push(getRequestErrorMessage(result.reason, "Não foi possível atualizar destinos."));
      }
      if (saved.status === "fulfilled") {
        for (const destination of saved.value) {
          if (!next.some((chat) => chat.id === destination.chat_id)) next.push({
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
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => void load(), 0);
    return () => clearTimeout(timer);
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
      const details = chat ? await api.getManagedWhatsAppChat(chat) : null;
      if (details && !details.can_manage) throw new Error("Sua conta precisa ser administradora para gerenciar este grupo.");
      if (details) setChats((current) => current.map((item) => item.id === details.id ? details : item));
      setEditor({ chat: details, mode, requestId: crypto.randomUUID() });
    });
  }

  function saveGroup(draft: WhatsAppGroupDraft, reusePhoto: boolean) {
    return run(async () => {
      if (!editor) return;
      const result = editor.mode === "edit" && editor.chat
        ? await api.updateWhatsAppGroup(editor.chat, draft)
        : await api.createWhatsAppGroup({ ...draft, source_id: editor.chat?.id ?? null, reuse_photo: reusePhoto, request_id: editor.requestId });
      setEditor(null);
      setNotice(result.warnings.length
        ? `${result.name}: ${result.warnings.join(" ")} Publicações desativadas até concluir configuração.`
        : `${result.name}: ${editor.mode === "create" ? "grupo criado" : "alterações salvas"}.`);
      await load();
    });
  }

  function saveRouting(chat: ManagedWhatsAppChat, categories: OfferCategory[] | null, enabled: boolean) {
    return run(async () => {
      const result = await api.saveWhatsAppRouting(chat, categories, enabled);
      setChats((current) => current.map((item) => item.id === chat.id ? { ...item, ...result } : item));
      setNotice(`${chat.name}: categorias e publicação atualizadas.`);
    });
  }

  function refreshChat(chat: ManagedWhatsAppChat) {
    return run(async () => {
      const result = await api.getManagedWhatsAppChat(chat);
      setChats((current) => current.map((item) => item.id === chat.id ? result : item));
    });
  }

  return { chats, isLoading, isBusy, errors, error, notice, editor, updatedAt,
    refresh: () => run(load), openEditor, closeEditor: () => setEditor(null), saveGroup, saveRouting, refreshChat };
}
