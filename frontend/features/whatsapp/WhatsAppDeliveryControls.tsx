"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { useWhatsAppPolicy } from "@/features/whatsapp/hooks/use-whatsapp-policy";
import type { WhatsAppPolicy } from "@/features/whatsapp/types";

const fields: { key: keyof WhatsAppPolicy; label: string; min: number; max: number }[] = [
  { key: "ttl_seconds", label: "Validade máxima (segundos)", min: 30, max: 600 },
  { key: "account_interval_seconds", label: "Intervalo por conta (segundos)", min: 1, max: 600 },
  { key: "channel_interval_seconds", label: "Intervalo por destino (segundos)", min: 1, max: 600 },
  { key: "max_per_hour", label: "Tentativas por hora / conta", min: 1, max: 3600 },
  { key: "max_per_day", label: "Tentativas por 24h / conta", min: 1, max: 10000 },
  { key: "burst_window_seconds", label: "Janela de rajada/coleta (segundos)", min: 5, max: 300 },
  { key: "burst_threshold", label: "Quantidade que caracteriza rajada", min: 6, max: 100 },
  { key: "start_hour_utc", label: "Início da publicação (hora UTC)", min: 0, max: 23 },
  { key: "end_hour_utc", label: "Fim da publicação (hora UTC)", min: 1, max: 24 },
];

export function WhatsAppDeliveryControls({ compact = false }: { compact?: boolean }) {
  const policy = useWhatsAppPolicy();
  const settings = policy.data?.settings;

  return <section className="space-y-4 rounded-xl border border-border p-4" aria-label="Controles de publicação WhatsApp">
    <h3 className="font-semibold">Fila e limites de publicação</h3>
    <p className="text-sm/6 text-muted-foreground">Ofertas do mesmo produto/variação e preço não se repetem no mesmo destino por 30 minutos, mesmo vindo de origens diferentes. Mudança de preço permite nova publicação.</p>
    {policy.error ? <div className="space-y-2"><p role="alert" className="text-sm text-destructive">{policy.error}</p><Button variant="outline" disabled={policy.isBusy} onClick={() => void policy.refresh()}>Atualizar controles</Button></div> : null}
    {!settings && !policy.error ? <p role="status" className="text-sm text-muted-foreground">Consultando regras de publicação…</p> : null}
    {settings ? <p className="text-sm/6 text-muted-foreground">Ofertas expiram em até {policy.data?.effective_ttl_seconds} segundos desde a origem, considerando também o limite do servidor, sem renovar prazo em retries. Ao detectar {settings.burst_threshold} ofertas em {settings.burst_window_seconds} segundos, mantemos somente as {policy.data?.burst_keep} mais recentes por canal. Cada oferta aguarda uma janela de coleta antes do envio. Intervalos mínimos: {settings.account_interval_seconds}s por conta e {settings.channel_interval_seconds}s por destino, com teto de {settings.max_per_hour}/hora e {settings.max_per_day}/24h por conta. Publicação das {settings.start_hour_utc}h às {settings.end_hour_utc}h UTC. Ofertas que não couberem no prazo são descartadas.</p> : null}
    {policy.data?.pauses.length ? <div className="space-y-3 rounded-lg bg-muted p-3"><h4 className="font-medium">Envios temporariamente pausados</h4><ul className="space-y-2 text-sm">{policy.data.pauses.map((pause) => <li key={pause.chat_id ?? "account"}><strong>{pause.chat_id ? `Destino ${pause.chat_id}` : "Conta WhatsApp"}</strong>: {pause.reason_message} Até {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(pause.paused_until))} (Brasília).</li>)}</ul>{!compact ? <Button variant="outline" disabled={policy.isBusy} onClick={() => void policy.resume()}>Retomar após corrigir conexão/permissões</Button> : null}</div> : null}
    {compact ? <Link className="text-sm font-medium text-primary underline" href="/settings#whatsapp">Gerenciar limites e pausas nas configurações</Link> : policy.draft ? <form className="space-y-4" onSubmit={(event) => { event.preventDefault(); void policy.save(); }}>
      <fieldset disabled={policy.isBusy} className="grid gap-4 sm:grid-cols-2">{fields.map((field) => <label key={field.key} className="space-y-2 text-sm font-medium">{field.label}<input className="h-11 w-full rounded-lg border border-border bg-background px-3" type="number" required step={1} min={field.min} max={field.max} value={Number.isFinite(policy.draft?.[field.key]) ? policy.draft?.[field.key] : ""} onChange={(event) => policy.change(field.key, event.target.valueAsNumber)} /></label>)}</fieldset>
      <p className="text-xs/5 text-muted-foreground">Janela UTC: 0–24 permite o dia inteiro (Brasília = UTC−3). Limites são controles editoriais, sem garantia contra banimento. Mudanças não recuperam ofertas expiradas ou descartadas.</p>
      <Button type="submit" disabled={policy.isBusy}>{policy.isBusy ? "Salvando…" : "Salvar limites WhatsApp"}</Button>
    </form> : null}
    {policy.message ? <p role="status" className="text-sm text-primary">{policy.message}</p> : null}
  </section>;
}
