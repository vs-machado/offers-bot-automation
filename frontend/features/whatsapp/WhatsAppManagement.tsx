"use client";

import { useState } from "react";
import { Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { WhatsAppConnection } from "@/features/whatsapp/WhatsAppConnection";
import { WhatsAppDeliveryControls } from "@/features/whatsapp/WhatsAppDeliveryControls";
import { WhatsAppChatCard } from "@/features/whatsapp/components/WhatsAppChatCard";
import { WhatsAppGroupForm } from "@/features/whatsapp/components/WhatsAppGroupForm";
import { useWhatsAppManagement } from "@/features/whatsapp/hooks/use-whatsapp-management";
import { useWhatsAppConnections } from "@/features/whatsapp/hooks/use-whatsapp-connections";
import type { WhatsAppConnectionSummary } from "@/features/whatsapp/types";

export function WhatsAppManagement() {
  const connections = useWhatsAppConnections();
  const [name, setName] = useState("");
  const selected = connections.connections.find((row) => row.id === connections.selectedId);
  return <>
    <section aria-label="Conexões WhatsApp" className="space-y-4 rounded-xl border p-4">
      <h3 className="font-semibold">Suas contas WhatsApp</h3>
      <p className="text-sm text-muted-foreground">Cada conexão representa um número, com QR, destinos, cotas e pausas próprios. Selecione uma conta para gerenciar. Telegram permanece independente.</p>
      {connections.error ? <p role="alert" className="text-sm text-destructive">{connections.error} <button className="underline" onClick={() => void connections.refresh()}>Tentar novamente</button></p> : null}
      <label className="block space-y-2 text-sm font-medium">Conta selecionada
        <select className="h-11 w-full rounded-lg border bg-background px-3" disabled={connections.isBusy} value={connections.selectedId ?? ""} onChange={(event) => connections.select(Number(event.target.value))}>
          {!connections.connections.length ? <option value="">Carregando conexões…</option> : null}
          {connections.connections.map((row) => <option key={row.id} value={row.id}>{row.name}{row.is_default ? " · principal" : ""}</option>)}
        </select>
      </label>
      <form className="flex flex-wrap items-end gap-3" onSubmit={(event) => { event.preventDefault(); void connections.save(name); }}>
        <label className="min-w-48 flex-1 space-y-2 text-sm font-medium">Nome da conexão
          <input required maxLength={100} className="h-11 w-full rounded-lg border bg-background px-3" value={name} onChange={(event) => setName(event.target.value)} placeholder="Ofertas · número 2" />
        </label>
        <Button type="submit" disabled={connections.isBusy || !name.trim() || !selected}>Adicionar conta</Button>
        <Button type="button" variant="outline" disabled={connections.isBusy || !name.trim() || !selected} onClick={() => void connections.save(name, true)}>Renomear selecionada</Button>
      </form>
      <p className="text-xs text-muted-foreground">Novas contas: 30–90s entre envios, mínimo 60s por destino, até 6 grupos habilitados e janela 7h–23h (Brasília). Capacidade de múltiplas sessões depende da instalação WAHA.</p>
    </section>
    {selected ? <ConnectionManagement key={selected.id} connectionId={selected.id} name={selected.name} connections={connections.connections} /> : null}
  </>;
}

function ConnectionManagement({ connectionId, name, connections }: { connectionId: number; name: string; connections: WhatsAppConnectionSummary[] }) {
  const [connectionStatus, setConnectionStatus] = useState("LOADING");
  const management = useWhatsAppManagement(connectionStatus, connectionId);
  const connected = connectionStatus === "WORKING";
  const [filter, setFilter] = useState<"all" | "group" | "channel" | "full">("all");
  const [search, setSearch] = useState("");
  const disabled = management.isBusy || management.isLoading;
  const visible = management.chats.filter((chat) =>
    (filter === "all" || (filter === "full" ? chat.is_full : chat.chat_type === filter)) && chat.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const fullCount = management.chats.filter((chat) => chat.is_full).length;

  return <>
    <section id="whatsapp-connection" aria-label="Conexão da conta WhatsApp" className="scroll-mt-32 space-y-3 rounded-xl border bg-muted/20 p-4 sm:p-5">
      <h3 className="text-sm font-semibold">Conexão: {name}</h3>
      <WhatsAppConnection connectionOnly connectionId={connectionId} busy={management.isBusy} onStatusChange={setConnectionStatus} onDisconnect={() => setConnectionStatus("STOPPED")} />
      <p className="text-sm text-muted-foreground">Ative ofertas nos grupos e canais abaixo para adicioná-los aos seus destinos. Canais disponíveis somente para administradores. Reconectar não reativa publicações automaticamente.</p>
    </section>
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <h3 className="text-lg font-semibold">Grupos e canais</h3>
        <p className="mt-2 max-w-prose text-sm/relaxed text-muted-foreground">Acompanhe lotação e escolha categorias de ofertas para cada destino.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" disabled={disabled || Boolean(management.editor)} onClick={() => void management.refresh()}><RefreshCw aria-hidden="true" className={`size-4 ${management.isLoading ? "animate-spin" : ""}`} />Atualizar</Button>
        <Button disabled={!connected || disabled || Boolean(management.editor)} onClick={() => void management.openEditor(null, "create")}><Plus aria-hidden="true" className="size-4" />Novo grupo</Button>
      </div>
    </header>
    <div aria-live="polite" className="space-y-2">
      {management.notice ? <p role="status" className="rounded-xl border bg-muted p-4 text-sm/6">{management.notice}</p> : null}
      {management.error ? <p role="alert" className="rounded-xl border border-destructive/40 p-4 text-sm text-destructive">{management.error}</p> : null}
      {management.errors.map((error) => <p key={error} role="alert" className="rounded-xl border p-4 text-sm">{error} <a href="#whatsapp-connection" className="text-primary underline">Ver conexão</a></p>)}
    </div>
    {management.editor ? <WhatsAppGroupForm key={management.editor.requestId} editor={management.editor} disabled={!connected || management.isBusy} onSave={management.saveGroup} onClose={management.closeEditor} /> : null}
    {fullCount ? <div className="rounded-xl border border-amber-500/50 bg-amber-500/5 p-4 text-sm">{fullCount} {fullCount === 1 ? "grupo lotado" : "grupos lotados"}. Use “Criar próximo grupo” para continuar série com mesmo perfil e categorias.</div> : null}
    <section aria-label="Seus grupos e canais" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" aria-label="Filtrar destinos">
          {([ ["all", "Todos"], ["group", "Grupos"], ["channel", "Canais"], ["full", "Lotados"] ] as const).map(([value, label]) => <Button key={value} variant={filter === value ? "secondary" : "ghost"} onClick={() => setFilter(value)} aria-pressed={filter === value}>{label}</Button>)}
        </div>
        <input type="search" aria-label="Buscar grupo ou canal" placeholder="Buscar grupo ou canal…" className="h-10 w-full rounded-lg border bg-background px-3 text-sm sm:w-64" value={search} onChange={(event) => setSearch(event.target.value)} />
      </div>
      <p className="text-xs text-muted-foreground">{management.chats.length} destinos · {management.isLoading ? "Consultando WhatsApp…" : `Última consulta: ${management.updatedAt || "—"}. Seguidores dos canais atualizados ao abrir esta página. Use Atualizar para consultar novamente.`}</p>
      {management.isLoading && !management.chats.length ? <p role="status" className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">Carregando grupos e canais…</p> : visible.length ? <div className="grid gap-4 xl:grid-cols-2">
        {visible.map((chat) => <WhatsAppChatCard key={`${chat.id}:${chat.destination_id}:${JSON.stringify(chat.categories)}`} chat={chat} connected={connected} disabled={disabled || Boolean(management.editor)}
          onEdit={() => void management.openEditor(chat, "edit")} onNext={() => void management.openEditor(chat, "create")}
          onRefresh={() => void management.refreshChat(chat)} onRouting={(categories, enabled) => management.saveRouting(chat, categories, enabled)} onRemove={() => management.removeDestination(chat)}
          otherConnections={connections.filter((row) => row.id !== connectionId)} onMove={(id) => management.moveDestination(chat, id)} />)}
      </div> : <div className="rounded-xl border border-dashed p-8 text-center">
        <h2 className="font-medium">Nenhum destino encontrado</h2><p className="mt-2 text-sm text-muted-foreground">Conecte seu WhatsApp, crie um grupo ou ajuste filtros. Canais exibidos somente quando sua conta é administradora.</p>
      </div>}
    </section>
    <WhatsAppDeliveryControls connectionId={connectionId} />
  </>;
}
