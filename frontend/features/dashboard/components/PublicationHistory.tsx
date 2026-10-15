"use client";

import { CircleAlert, Clock3, History, Hourglass, Inbox, RefreshCw, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDeliveryHistory } from "@/features/dashboard/hooks/use-delivery-history";
import type { DeliveryHistoryData, DeliveryStatus } from "@/features/dashboard/types";

const statusLabels: Record<DeliveryStatus, string> = {
  queued: "Na fila", retrying: "Nova tentativa", sending: "Enviando", sent: "Enviada",
  failed: "Falhou", expired: "Expirada", cancelled: "Cancelada", uncertain: "Sem confirmação",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(value));
}

export function PublicationHistory({ initialData }: { initialData: DeliveryHistoryData | null }) {
  const history = useDeliveryHistory(initialData);
  const counts = history.data?.counts;
  const metrics = [
    { label: "Enviadas", value: counts?.sent ?? 0, icon: Send },
    { label: "Falhas ou sem confirmação", value: (counts?.failed ?? 0) + (counts?.uncertain ?? 0), icon: CircleAlert },
    { label: "Expiradas", value: counts?.expired ?? 0, icon: Hourglass },
    { label: "Aguardando envio", value: (counts?.queued ?? 0) + (counts?.retrying ?? 0) + (counts?.sending ?? 0), icon: Clock3 },
  ];

  return (
    <section className="mt-6 w-full space-y-6" aria-labelledby="publication-history-title" aria-busy={history.isLoading}>
      {counts ? <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;

          return (
            <Card key={metric.label} className="py-0">
              <CardContent className="flex min-h-44 items-start justify-between gap-4 p-6 sm:p-7">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-muted-foreground sm:text-base">{metric.label}</p>
                  <p className="mt-5 text-4xl font-bold tracking-tight tabular-nums sm:text-5xl">{metric.value}</p>
                </div>
                <div className="flex size-12 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                  <Icon aria-hidden="true" className="size-6" />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div> : null}
      <Card className="min-h-112 sm:[--card-spacing:--spacing(8)]">
        <CardHeader className="gap-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0"><CardTitle id="publication-history-title" className="flex items-center gap-3 text-xl font-semibold sm:text-2xl"><History aria-hidden="true" className="size-6 shrink-0 text-primary" />Histórico de publicações</CardTitle><p className="mt-2 text-sm text-muted-foreground sm:text-base">Uma linha por destino. Horários de Brasília. Atualização a cada 30 segundos.</p></div>
            <Button variant="outline" disabled={history.isLoading} onClick={() => void history.loadHistory(history.page, history.status)}><RefreshCw className="size-4" />{history.isLoading ? "Atualizando…" : "Atualizar"}</Button>
          </div>
          <label className="flex items-center gap-3 text-sm">Resultado
            <select className="rounded-lg border border-border bg-background p-2 text-foreground" value={history.status} disabled={history.isLoading} onChange={(event) => void history.loadHistory(1, event.target.value as DeliveryStatus | "")}>
              <option value="">Todos</option>{Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
        </CardHeader>
        <CardContent>
          {history.error ? <p role="alert" className="mb-4 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">{history.error}</p> : null}
          {history.data ? <>
            {history.data.items.length ? <ul className="divide-y divide-border">{history.data.items.map((delivery) => <li key={delivery.id} className="space-y-3 py-6">
              <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="min-w-0 wrap-break-word font-semibold">{delivery.title ?? "Promoção registrada antes da atualização do histórico"}</h3><span className={`rounded-full px-3 py-1 text-xs font-semibold ${delivery.status === "sent" ? "bg-primary/10 text-primary" : ["failed", "uncertain"].includes(delivery.status) ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground"}`}>{statusLabels[delivery.status]}</span></div>
              <p className="text-sm text-muted-foreground">{delivery.platform ? `${delivery.platform} · ` : ""}{delivery.destination_title ?? delivery.chat_id} · {formatDate(delivery.created_at)}</p>
              {delivery.reason_message ? <p className="rounded-lg bg-muted p-3 text-sm">{delivery.reason_message}</p> : null}
              <p className="text-xs text-muted-foreground">{delivery.stage === "affiliate" ? "Conversão do link" : delivery.stage === "processing" ? "Preparação da promoção" : "Publicação no Telegram"} · {delivery.attempts === 0 ? "Envio não iniciado" : `${delivery.attempts} ${delivery.attempts === 1 ? "tentativa" : "tentativas"}`} · Última atualização: {formatDate(delivery.updated_at)}</p>
            </li>)}</ul> : <div className="flex min-h-60 flex-col items-center justify-center gap-4 py-10 text-center text-muted-foreground"><Inbox aria-hidden="true" className="size-10 text-primary" /><p className="max-w-md text-base">{history.status ? "Nenhuma publicação com esse resultado." : "Nenhuma publicação registrada ainda. As próximas tentativas aparecerão aqui."}</p></div>}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4"><p className="text-sm text-muted-foreground">{history.data.total} {history.data.total === 1 ? "registro" : "registros"} · Página {history.page}</p><div className="flex gap-2"><Button variant="outline" disabled={history.isLoading || history.page === 1} onClick={() => void history.loadHistory(history.page - 1, history.status)}>Anterior</Button><Button variant="outline" disabled={history.isLoading || history.page * 20 >= history.data.total} onClick={() => void history.loadHistory(history.page + 1, history.status)}>Próxima</Button></div></div>
          </> : null}
        </CardContent>
      </Card>
    </section>
  );
}
