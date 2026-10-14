"use client";

import { useState, type FormEvent } from "react";

import { removeSourceGroup, saveSourceGroup } from "@/features/admin/api/admin-client";
import type { AdminSourceGroup, SourceGroupInput } from "@/features/admin/types";

const emptyInput: SourceGroupInput = { label: "", url: "", enabled: true };

export function useSourceCatalog(initialGroups: AdminSourceGroup[]) {
  const [groups, setGroups] = useState(initialGroups);
  const [input, setInput] = useState<SourceGroupInput>(emptyInput);
  const [editingId, setEditingId] = useState<number>();
  const [deletingId, setDeletingId] = useState<number>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  function cancelEdit() {
    setEditingId(undefined);
    setInput(emptyInput);
  }

  function editGroup(group: AdminSourceGroup) {
    setEditingId(group.id);
    setInput({ label: group.label, url: group.url, enabled: group.enabled });
    setError("");
    setNotice("");
  }

  async function mutate(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice("Catalog updated. The Telegram reader applies changes within 30 seconds.");
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not update the catalog.");
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await mutate(async () => {
      const saved = await saveSourceGroup(input, editingId);
      setGroups((current) => [...current.filter((group) => group.id !== saved.id), saved].sort((a, b) => a.id - b.id));
      cancelEdit();
    });
  }

  async function toggleGroup(group: AdminSourceGroup) {
    await mutate(async () => {
      const saved = await saveSourceGroup({ label: group.label, url: group.url, enabled: !group.enabled }, group.id);
      setGroups((current) => current.map((item) => item.id === saved.id ? saved : item));
      if (editingId === saved.id) setInput((current) => ({ ...current, enabled: saved.enabled }));
    });
  }

  async function deleteGroup(group: AdminSourceGroup) {
    await mutate(async () => {
      await removeSourceGroup(group.id);
      setGroups((current) => current.filter((item) => item.id !== group.id));
      setDeletingId(undefined);
      if (editingId === group.id) cancelEdit();
    });
  }

  return { groups, input, setInput, editingId, deletingId, setDeletingId, busy, error, notice, cancelEdit, editGroup, submit, toggleGroup, deleteGroup };
}
