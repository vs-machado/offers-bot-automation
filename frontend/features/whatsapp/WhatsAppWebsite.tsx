"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { useWhatsAppWebsite } from "@/features/whatsapp/hooks/use-whatsapp-website";
import type { WhatsAppConnectionSummary } from "@/features/whatsapp/types";

export function WhatsAppWebsite({ connections }: { connections: WhatsAppConnectionSummary[] }) {
  const site = useWhatsAppWebsite();
  const [recoveryId, setRecoveryId] = useState("");
  const draft = site.draft;
  const connection = connections.find((row) => row.id === draft?.connection_id);
  const groups = site.destinations.filter((row) => row.connection_id === connection?.id || (connection?.is_default && row.connection_id === null));
  const eligibleGroups = groups.filter((row) => row.enabled);
  const selectedRecoveryId = recoveryId || (eligibleGroups[0] ? String(eligibleGroups[0].id) : "");
  const inputClass = "h-11 w-full rounded-lg border bg-background px-3";

  return <section aria-label="Site e rotação automática de grupos" className="space-y-4 rounded-xl border p-4">
    <h3 className="font-semibold">Site e rotação automática de grupos</h3>
    <p className="text-sm text-muted-foreground">Ao habilitar, o bot cria um grupo e guarda o convite no PostgreSQL. Ao atingir o limite, cria o próximo sem interromper ofertas nos anteriores. Monitor: 60s; entrada vence após 180s sem confirmação.</p>
    <p className="text-xs text-muted-foreground">Salve para gerar seu link público. Configure esse link no botão do site uma única vez; as próximas trocas são automáticas. Cloudflare hospeda apenas a página estática.</p>
    {site.error ? <p role="alert" className="text-sm text-destructive">{site.error}</p> : null}
    <Button variant="outline" disabled={site.isBusy} onClick={() => void site.refresh()}>Atualizar estado</Button>
    {draft ? <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); void site.save(); }}>
      <fieldset disabled={site.isBusy} className="grid gap-4 sm:grid-cols-2">
        <label className="space-y-2 text-sm font-medium">URL do site
          <input className={inputClass} type="url" maxLength={255} placeholder="https://seu-projeto.pages.dev" value={draft.website_url} onChange={(event) => site.change("website_url", event.target.value)} />
        </label>
        <label className="space-y-2 text-sm font-medium">Conta responsável pelo site
          <select className={inputClass} value={draft.connection_id ?? ""} onChange={(event) => site.change("connection_id", event.target.value ? Number(event.target.value) : null)}>
            <option value="">Selecione uma conta</option>
            {connections.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label className="space-y-2 text-sm font-medium">Grupo modelo (opcional)
          <select className={inputClass} value={draft.template_destination_id ?? ""} onChange={(event) => site.selectTemplate(event.target.value ? Number(event.target.value) : null)}>
            <option value="">Criar com nome e descrição abaixo</option>
            {groups.map((row) => <option key={row.id} value={row.id}>{row.title || row.chat_id}</option>)}
          </select>
          <span className="text-xs font-normal text-muted-foreground">Ao escolher, preenche o nome padrão dos próximos grupos.</span>
        </label>
        <label className="space-y-2 text-sm font-medium">Nome padrão dos grupos
          <input className={inputClass} required maxLength={90} value={draft.group_name} onChange={(event) => site.change("group_name", event.target.value)} />
        </label>
        <label className="space-y-2 text-sm font-medium">Limite operacional de entrada
          <input className={inputClass} type="number" required min={2} max={1024} value={draft.entry_limit} onChange={(event) => site.change("entry_limit", event.target.valueAsNumber)} />
        </label>
        <label className="space-y-2 text-sm font-medium">Margem abaixo da capacidade informada pelo WhatsApp
          <input className={inputClass} type="number" required min={1} max={1022} value={draft.safety_margin} onChange={(event) => site.change("safety_margin", event.target.valueAsNumber)} />
        </label>
        {draft.template_destination_id ? null : <label className="space-y-2 text-sm font-medium">Descrição (sem modelo)
          <textarea className="min-h-24 w-full rounded-lg border bg-background p-3" maxLength={2048} value={draft.description} onChange={(event) => site.change("description", event.target.value)} />
        </label>}
        <label className="flex min-h-11 items-center gap-3 text-sm font-medium">
          <Checkbox disabled={site.isBusy} checked={draft.enabled} onCheckedChange={(enabled) => site.change("enabled", enabled === true)} />
          Habilitar criação e rotação automáticas
        </label>
      </fieldset>
      <p className="text-xs text-muted-foreground">Grupos novos permitem mensagens apenas de administradores. Modelo copia descrição, foto e categorias; participantes não são copiados. Limite de grupos habilitados por conta continua valendo. Sem capacidade informada pelo provedor, vale o limite operacional configurado.</p>
      <Button type="submit" disabled={site.isBusy}>Salvar integração do site</Button>
    </form> : null}
    {site.entryUrl ? <div className="space-y-2">
      <label className="block space-y-2 text-sm font-medium">Seu link público de entrada
        <input className={inputClass} readOnly value={site.entryUrl} onFocus={(event) => event.target.select()} />
      </label>
      <p className="text-xs text-muted-foreground">Copie para whatsappEntryUrl no site.config.json do site e publique uma vez. O link permanece igual quando o grupo muda. Não é uma credencial de acesso ao painel.</p>
      <a className="text-sm text-primary underline" href={site.entryUrl} target="_blank" rel="noopener noreferrer">Testar entrada pública</a>
    </div> : null}
    {site.data ? <div className="space-y-2 text-sm" aria-live="polite">
      <p>Grupo ativo: {site.destinations.find((row) => row.id === site.data?.active_destination_id)?.title || site.data.active_destination_id || "aguardando"} · Membros: {site.data.member_count ?? "desconhecido"}</p>
      <p>Última verificação: {site.data.observed_at ? new Date(site.data.observed_at).toLocaleString("pt-BR") : "aguardando"}</p>
      {site.data.last_error ? <p role="alert" className="text-destructive">{site.data.last_error}</p> : null}
      {site.data.needs_recovery ? <p className="text-destructive">Criação iniciada sem confirmação. Confira o WhatsApp e cadastre o grupo na lista antes de adotá-lo. Bot não repete criação incerta.</p> : null}
    </div> : null}
    <div className="space-y-3 rounded-lg border p-3">
      <p className="text-sm font-medium">Grupo inicial do site</p>
      <p className="text-xs text-muted-foreground">Use grupo que já está rodando como entrada do site. Com um único grupo elegível, bot escolhe automaticamente; com vários, selecione abaixo. Grupo deve ser administrado por esta conta, ter ofertas habilitadas e configurações concluídas.</p>
      <select aria-label="Grupo inicial do site" className={inputClass} value={selectedRecoveryId} onChange={(event) => setRecoveryId(event.target.value)}>
        <option value="">Selecione um grupo</option>
        {eligibleGroups.map((row) => <option key={row.id} value={row.id}>{row.title || row.chat_id}</option>)}
      </select>
      <Button variant="outline" disabled={site.isBusy || !selectedRecoveryId} onClick={() => void site.save(Number(selectedRecoveryId))}>Usar grupo existente como entrada</Button>
    </div>
    {site.message ? <p role="status" className="text-sm text-primary">{site.message}</p> : null}
  </section>;
}
