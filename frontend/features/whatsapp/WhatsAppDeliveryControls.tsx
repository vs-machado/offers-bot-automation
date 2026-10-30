"use client";

import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useWhatsAppPolicy } from "@/features/whatsapp/hooks/use-whatsapp-policy";
import type { WhatsAppPolicy } from "@/features/whatsapp/types";

const fields: { key: Exclude<keyof WhatsAppPolicy, "posting_timezone">; label: string; min: number; max: number; optional?: boolean }[] = [
  { key: "ttl_seconds", label: "Validade máxima (segundos)", min: 30, max: 600 },
  { key: "account_interval_seconds", label: "Intervalo mínimo por conexão (segundos)", min: 1, max: 600 },
  { key: "account_interval_max_seconds", label: "Intervalo máximo aleatório (vazio = fixo)", min: 1, max: 600, optional: true },
  { key: "channel_interval_seconds", label: "Intervalo por destino (segundos)", min: 1, max: 600 },
  { key: "max_per_hour", label: "Tentativas por hora / conta", min: 1, max: 3600 },
  { key: "max_per_day", label: "Tentativas por 24h / conta", min: 1, max: 10000 },
  { key: "destination_max_per_day", label: "Tentativas por 24h / destino (vazio = sem cota adicional)", min: 1, max: 10000, optional: true },
  { key: "max_groups", label: "Grupos habilitados por conexão", min: 1, max: 6 },
  { key: "burst_window_seconds", label: "Janela de detecção de rajada (segundos)", min: 5, max: 300 },
  { key: "collection_seconds", label: "Coleta inicial por oferta do canal (segundos)", min: 5, max: 300 },
  { key: "burst_threshold", label: "Quantidade que caracteriza rajada", min: 6, max: 100 },
  { key: "start_hour_utc", label: "Início da publicação (hora no fuso escolhido)", min: 0, max: 23 },
  { key: "end_hour_utc", label: "Fim da publicação (hora no fuso escolhido)", min: 1, max: 24 },
];

export function WhatsAppDeliveryControls({ compact = false, connectionId }: { compact?: boolean; connectionId?: number }) {
  const policy = useWhatsAppPolicy(connectionId);
  const settings = policy.data?.settings;

  return <section className="space-y-4 rounded-xl border border-border p-4" aria-label="Controles de publicação WhatsApp">
    {policy.error ? <div className="space-y-2"><p role="alert" className="text-sm text-destructive">{policy.error}</p><Button variant="outline" disabled={policy.isBusy} onClick={() => void policy.refresh()}>Atualizar controles</Button></div> : null}
    {policy.data?.pauses.length ? <div className="space-y-3 rounded-lg bg-muted p-3"><h4 className="font-medium">Envios temporariamente pausados</h4><ul className="space-y-2 text-sm">{policy.data.pauses.map((pause) => <li key={pause.chat_id ?? "account"}><strong>{pause.chat_id ? `Destino ${pause.chat_id}` : "Conta WhatsApp"}</strong>: {pause.reason_message} Até {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(pause.paused_until))} (Brasília).</li>)}</ul>{!compact ? <Button variant="outline" disabled={policy.isBusy} onClick={() => void policy.resume()}>Retomar após corrigir conexão/permissões</Button> : null}</div> : null}
    <details className="group/options">
      <summary className="flex min-h-10 cursor-pointer list-none items-center justify-between gap-3 rounded-lg text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring [&::-webkit-details-marker]:hidden">
        <span className="font-semibold">Opções de publicação</span>
        <span className="flex items-center gap-2 text-muted-foreground">
          <span className="group-open/options:hidden">Ver opções</span>
          <span className="hidden group-open/options:inline">Ocultar opções</span>
          <ChevronDown aria-hidden="true" className="size-4 transition-transform group-open/options:rotate-180" />
        </span>
      </summary>
      <div className="space-y-4 border-t pt-4">
        <p className="text-sm/6 text-muted-foreground">Ofertas do mesmo produto/variação e preço não se repetem no mesmo destino por 30 minutos, mesmo vindo de origens diferentes. Mudança de preço permite nova publicação.</p>
        {!settings && !policy.error ? <p role="status" className="text-sm text-muted-foreground">Consultando regras de publicação…</p> : null}
        {settings ? <p className="text-sm/6 text-muted-foreground">Validade efetiva: {policy.data?.effective_ttl_seconds}s desde origem, sem renovar prazo. Rajadas mantêm as {policy.data?.burst_keep} ofertas pendentes mais recentes por canal, em janela de {settings.burst_window_seconds}s; coleta inicial independente de {settings.collection_seconds}s por oferta do canal. Espaçamento entre envios desta conexão: {settings.account_interval_seconds}–{settings.account_interval_max_seconds ?? settings.account_interval_seconds}s; por destino: pelo menos {settings.channel_interval_seconds}s. Cotas compartilhadas pelos grupos/canais desta conexão: {settings.max_per_hour}/hora e {settings.max_per_day}/24h. Cota adicional por destino: {settings.destination_max_per_day ?? "não definida"}/24h. Até {settings.max_groups} grupos habilitados. Janela: {settings.start_hour_utc}h–{settings.end_hour_utc}h ({settings.posting_timezone}). Ofertas que não cabem no prazo são descartadas. Telegram recebe conforme chegam, sem estes controles.</p> : null}
        {compact ? (
          <Link className="text-sm font-medium text-primary underline" href="/settings/destinations#whatsapp">Gerenciar limites e pausas nas configurações</Link>
        ) : policy.draft ? (
          <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); void policy.save(); }}>
            <fieldset disabled={policy.isBusy} className="grid gap-4 sm:grid-cols-2">
              {fields.map((field) => (
                <label key={field.key} className="space-y-2 text-sm font-medium">
                  {field.label}
                  <input
                    className="h-11 w-full rounded-lg border border-border bg-background px-3"
                    type="number"
                    required={!field.optional}
                    step={1}
                    min={field.min}
                    max={field.max}
                    value={Number.isFinite(policy.draft?.[field.key]) ? policy.draft?.[field.key] ?? "" : ""}
                    onChange={(event) => policy.change(field.key, field.optional && event.target.value === "" ? null : event.target.valueAsNumber)}
                  />
                </label>
              ))}
              <label className="space-y-2 text-sm font-medium">Fuso horário (IANA)
                <input className="h-11 w-full rounded-lg border bg-background px-3" required value={policy.draft.posting_timezone} onChange={(event) => policy.change("posting_timezone", event.target.value)} placeholder="America/Sao_Paulo" />
              </label>
            </fieldset>
            <p className="text-xs/5 text-muted-foreground">Janela 0–24 permite dia inteiro. Intervalo aleatório é sorteado uma vez por tentativa e preservado durante esperas. Cotas contam tentativas, inclusive falhas, em janelas móveis. Limites são controles editoriais, sem garantia contra banimento. Mudanças não recuperam ofertas expiradas ou descartadas.</p>
            <Button type="submit" disabled={policy.isBusy}>{policy.isBusy ? "Salvando…" : "Salvar limites WhatsApp"}</Button>
          </form>
        ) : null}
      </div>
    </details>
    {policy.message ? <p role="status" className="text-sm text-primary">{policy.message}</p> : null}
  </section>;
}
