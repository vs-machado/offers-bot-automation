"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SettingsState } from "@/features/settings/hooks/use-settings";
import type { DestinationSummary } from "@/shared/contracts/user-config";

export function DestinationSettings({ settings }: { settings: SettingsState }) {
  const [editingId, setEditingId] = useState<number | undefined>();
  const [chatId, setChatId] = useState("");
  const [title, setTitle] = useState("");
  const [chatType, setChatType] = useState("group");
  const [enabled, setEnabled] = useState(true);
  const [removingId, setRemovingId] = useState<number | null>(null);
  function reset() { setEditingId(undefined); setChatId(""); setTitle(""); setChatType("group"); setEnabled(true); }
  function edit(destination: DestinationSummary) { setEditingId(destination.id); setChatId(destination.chat_id); setTitle(destination.title ?? ""); setChatType(destination.chat_type ?? "group"); setEnabled(destination.enabled); }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (await settings.saveDestination({ chat_id: chatId.trim(), title: title.trim() || null, chat_type: chatType, enabled }, editingId)) reset();
  }
  async function remove(id: number) {
    if (await settings.removeDestination(id)) {
      setRemovingId(null);
      if (editingId === id) reset();
    }
  }
  const inputClass = "h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground";
  return <Card id="destinations" className="scroll-mt-6"><CardHeader><CardTitle>Onde publicar</CardTitle><p className="text-sm/6 text-muted-foreground">Adicione @tgtestoffersbot como administrador e permita o envio de mensagens e fotos. Ao habilitar um destino, verificamos a permissão do bot.</p></CardHeader><CardContent>
    <ul className="mb-6 divide-y divide-border">{settings.destinations.map((destination) => <li key={destination.id} className="space-y-3 py-4"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-medium">{destination.title || destination.chat_id}</p><p className="text-sm text-muted-foreground">{destination.chat_id} · {destination.enabled ? "Habilitado" : "Desativado"}</p></div><div className="flex flex-wrap gap-2"><Button variant="outline" disabled={Boolean(settings.busy)} onClick={() => edit(destination)}>Editar</Button><Button variant="outline" disabled={Boolean(settings.busy)} onClick={() => void settings.toggleDestination(destination)}>{destination.enabled ? "Desativar" : "Habilitar"}</Button><Button variant="outline" disabled={Boolean(settings.busy)} onClick={() => setRemovingId(destination.id)}>Remover</Button></div></div>{removingId === destination.id ? <div className="rounded-lg bg-muted p-3 text-sm"><p>Remover esse destino? O bot deixará de publicar nele.</p><div className="mt-3 flex gap-2"><Button variant="destructive" disabled={Boolean(settings.busy)} onClick={() => void remove(destination.id)}>Confirmar remoção</Button><Button variant="outline" disabled={Boolean(settings.busy)} onClick={() => setRemovingId(null)}>Cancelar</Button></div></div> : null}</li>)}</ul>
    {!settings.destinations.length ? <p className="mb-4 text-sm text-muted-foreground">Nenhum destino cadastrado ainda.</p> : null}
    <form onSubmit={submit} className="space-y-4 rounded-xl border border-border p-4"><h3 className="font-semibold">{editingId ? "Editar destino" : "Adicionar destino"}</h3><fieldset disabled={Boolean(settings.busy)} className="grid gap-4 sm:grid-cols-2"><label className="space-y-2 text-sm font-medium">ID do grupo ou canal<input className={inputClass} required pattern="-?[0-9]+" maxLength={100} title="Informe o ID numérico do Telegram, mantendo o sinal de menos." placeholder="Exemplo: -1001234567890" value={chatId} onChange={(event) => setChatId(event.target.value)} /></label><label className="space-y-2 text-sm font-medium">Nome para identificar o destino<input className={inputClass} maxLength={255} value={title} onChange={(event) => setTitle(event.target.value)} /></label><label className="space-y-2 text-sm font-medium">Tipo<select className={inputClass} value={chatType} onChange={(event) => setChatType(event.target.value)}><option value="group">Grupo</option><option value="channel">Canal</option></select></label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />Habilitar publicação neste destino</label></fieldset><div className="flex gap-2"><Button type="submit" disabled={Boolean(settings.busy)}>{settings.busy === "destinations" ? "Salvando…" : "Salvar destino"}</Button>{editingId ? <Button type="button" variant="outline" disabled={Boolean(settings.busy)} onClick={reset}>Cancelar edição</Button> : null}</div></form>
  </CardContent></Card>;
}
