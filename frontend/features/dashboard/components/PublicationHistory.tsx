"use client";

import {
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  ChevronsLeft,
  ChevronsRight,
  CircleAlert,
  Clock3,
  Hourglass,
  Inbox,
  RefreshCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { SelectField } from "@/components/ui/select";
import { PublicationRow } from "@/features/dashboard/components/PublicationRow";
import { useDeliveryHistory } from "@/features/dashboard/hooks/use-delivery-history";
import { deliveryStatusLabels } from "@/features/dashboard/lib/delivery-presentation";
import { groupPublications } from "@/features/dashboard/lib/group-publications";
import type {
  DeliveryHistoryData,
  DeliveryStatus,
} from "@/features/dashboard/types";

const countFormatter = new Intl.NumberFormat("pt-BR");

export function PublicationHistory({
  initialData,
}: {
  initialData: DeliveryHistoryData | null;
}) {
  const history = useDeliveryHistory(initialData);
  const counts = history.data?.counts;
  const publications = groupPublications(history.data?.items ?? []);
  const metrics = [
    { label: "Enviadas", value: counts?.sent ?? 0, icon: CheckCheck },
    {
      label: "Aguardando",
      value:
        (counts?.queued ?? 0) +
        (counts?.retrying ?? 0) +
        (counts?.sending ?? 0),
      icon: Clock3,
    },
    {
      label: "Falhas / incertas",
      value: (counts?.failed ?? 0) + (counts?.uncertain ?? 0),
      icon: CircleAlert,
    },
    { label: "Expiradas", value: counts?.expired ?? 0, icon: Hourglass },
  ];
  const total = history.data?.total ?? 0;
  const pageCount = Math.max(1, Math.ceil(total / 20));
  const firstRecord = total > 0 ? (history.page - 1) * 20 + 1 : 0;
  const lastRecord = Math.min(history.page * 20, total);

  return (
    <section
      className="flex min-h-0 flex-1 flex-col gap-4"
      aria-labelledby="publication-history-title"
    >
      <Card className="shrink-0 gap-0 py-0 shadow-none ring-1 ring-border">
        <dl className="grid grid-cols-4">
          {metrics.map(({ icon: Icon, ...metric }, index) => (
            <div
              key={metric.label}
              className={`min-w-0 p-2 sm:p-5 ${index > 0 ? "border-l" : ""}`}
            >
              <dt className="flex min-h-8 items-center justify-between gap-2 text-xs font-medium text-muted-foreground sm:min-h-0 sm:text-sm">
                {metric.label}
                <Icon
                  aria-hidden="true"
                  className="hidden size-4 shrink-0 sm:block"
                />
              </dt>
              <dd className="mt-1 text-xl font-semibold tracking-tight tabular-nums sm:mt-2 sm:text-3xl">
                {counts ? countFormatter.format(metric.value) : "—"}
              </dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card className="flex min-h-0 flex-1 flex-col gap-0 overflow-hidden py-0 shadow-none ring-1 ring-border">
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b p-4 sm:px-5">
          <div>
            <h2
              id="publication-history-title"
              className="text-base font-semibold"
            >
              Publicações
            </h2>
            <p className="mt-1 hidden text-xs text-muted-foreground sm:block">
              {history.status
                ? "Ofertas com esse resultado em pelo menos um destino. Abra para ver todos."
                : "Uma linha por oferta. Abra para acompanhar cada grupo ou canal."}
            </p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <label htmlFor="delivery-platform" className="sr-only">Filtrar por loja</label>
            <SelectField
              id="delivery-platform"
              className="flex-1 sm:w-40 sm:flex-none"
              value={history.platform}
              disabled={history.isLoading}
              options={[
                { value: "", label: "Todas as lojas" },
                { value: "amazon", label: "Amazon" },
                { value: "shopee", label: "Shopee" },
                { value: "mercado_livre", label: "Mercado Livre" },
                { value: "aliexpress", label: "AliExpress" },
              ]}
              onValueChange={(value) => void history.loadHistory(1, history.status, value)}
            />
            <label htmlFor="delivery-status" className="sr-only">
              Filtrar por resultado
            </label>
            <SelectField
              id="delivery-status"
              className="flex-1 sm:w-48 sm:flex-none"
              value={history.status}
              disabled={history.isLoading}
              options={[
                { value: "", label: "Todos os resultados" },
                ...Object.entries(deliveryStatusLabels).map(
                  ([value, label]) => ({ value, label }),
                ),
              ]}
              onValueChange={(value) =>
                void history.loadHistory(1, value as DeliveryStatus | "")
              }
            />
            <Button
              variant="outline"
              className="min-h-11 min-w-11 motion-reduce:transition-none"
              disabled={history.isLoading}
              aria-label={
                history.isLoading
                  ? "Atualizando publicações"
                  : "Atualizar publicações"
              }
              onClick={() =>
                void history.loadHistory(history.page, history.status)
              }
            >
              <RefreshCw
                aria-hidden="true"
                className={`size-4 ${history.isLoading ? "animate-spin motion-reduce:animate-none" : ""}`}
              />
              <span className="hidden sm:inline">Atualizar</span>
            </Button>
          </div>
        </div>

        {history.error ? (
          <div
            role="alert"
            className="m-4 flex items-start gap-2 rounded-xl border border-destructive/20 bg-background p-3 text-sm text-destructive"
          >
            <CircleAlert
              aria-hidden="true"
              className="mt-0.5 size-4 shrink-0"
            />
            <p>{history.error}</p>
          </div>
        ) : null}
        <div
          aria-busy={history.isLoading}
          tabIndex={0}
          role="region"
          aria-label="Lista de publicações"
          className="min-h-0 flex-1 overflow-y-auto overscroll-contain outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
        >
          {history.data?.items.length ? (
            <>
              <div
                aria-hidden="true"
                className="sticky top-0 z-10 hidden grid-cols-[minmax(0,1fr)_140px_132px_104px_16px] gap-4 border-b bg-card px-5 py-3 text-xs font-medium text-muted-foreground md:grid xl:grid-cols-[minmax(0,1fr)_104px_160px_132px_104px_16px]"
              >
                <span>Oferta</span>
                <span className="hidden xl:block">Loja</span>
                <span>Destinos · envios</span>
                <span>Resultado</span>
                <span>Último registro</span>
                <span className="sr-only">Detalhes</span>
              </div>
              <ul className="divide-y" aria-label="Histórico de publicações">
                {publications.map((publication) => (
                  <PublicationRow key={publication.id} publication={publication} />
                ))}
              </ul>
            </>
          ) : (
            <div className="flex min-h-64 flex-col items-center justify-center px-6 py-12 text-center">
              <span className="mb-4 flex size-12 items-center justify-center rounded-2xl border bg-muted/50">
                <Inbox
                  aria-hidden="true"
                  className="size-5 text-muted-foreground"
                />
              </span>
              <h3 className="text-sm font-medium">
                {!history.data
                  ? "Histórico indisponível"
                   : history.status || history.platform
                     ? "Nenhuma publicação com esses filtros"
                    : "Suas próximas ofertas aparecem aqui"}
              </h3>
              <p className="mt-2 max-w-sm text-sm/relaxed text-muted-foreground">
                {!history.data
                  ? "Use Atualizar para tentar carregar seus envios novamente."
                   : history.status || history.platform
                     ? "Escolha outra loja ou resultado, ou volte para todas as publicações."
                    : "Quando uma oferta for processada, você poderá acompanhar cada destino e resultado por aqui."}
              </p>
               {history.status || history.platform ? (
                <Button
                  variant="outline"
                  className="mt-4 min-h-11 motion-reduce:transition-none"
                  disabled={history.isLoading}
                   onClick={() => void history.loadHistory(1, "", "")}
                >
                  Ver todas as publicações
                </Button>
              ) : null}
            </div>
          )}
        </div>

        {history.data ? (
          <footer className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t px-4 py-3 sm:px-5">
            <p
              role="status"
              className="text-xs text-muted-foreground tabular-nums"
            >
              {countFormatter.format(firstRecord)}–
              {countFormatter.format(lastRecord)} de{" "}
              {countFormatter.format(total)}
              <span> ofertas</span>
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                className="min-h-11 min-w-11"
                disabled={history.isLoading || history.page === 1}
                onClick={() => void history.loadHistory(1, history.status)}
                aria-label="Primeira página"
              >
                <ChevronsLeft aria-hidden="true" className="size-4" />
              </Button>
              <Button
                variant="ghost"
                className="min-h-11 min-w-11 motion-reduce:transition-none"
                disabled={history.isLoading || history.page === 1}
                onClick={() =>
                  void history.loadHistory(history.page - 1, history.status)
                }
                aria-label="Página anterior"
              >
                <ChevronLeft aria-hidden="true" className="size-4" />
              </Button>
              <form
                className="flex items-center gap-2 text-xs text-muted-foreground tabular-nums"
                onSubmit={(event) => {
                  event.preventDefault();
                  const value = Number(new FormData(event.currentTarget).get("page"));
                  if (Number.isInteger(value) && value >= 1 && value <= pageCount) {
                    void history.loadHistory(value, history.status);
                  }
                }}
              >
                <label htmlFor="publication-page" className="sr-only">Número da página</label>
                <input
                  key={history.page}
                  id="publication-page"
                  name="page"
                  type="number"
                  min={1}
                  max={pageCount}
                  required
                  defaultValue={history.page}
                  disabled={history.isLoading}
                  className="h-11 w-16 rounded-lg border bg-background px-2 text-center text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
                <span>/ {countFormatter.format(pageCount)}</span>
                <Button type="submit" variant="outline" disabled={history.isLoading}>Ir</Button>
              </form>
              <Button
                variant="ghost"
                className="min-h-11 min-w-11 motion-reduce:transition-none"
                disabled={history.isLoading || history.page >= pageCount}
                onClick={() =>
                  void history.loadHistory(history.page + 1, history.status)
                }
                aria-label="Próxima página"
              >
                <ChevronRight aria-hidden="true" className="size-4" />
              </Button>
              <Button
                variant="ghost"
                className="min-h-11 min-w-11"
                disabled={history.isLoading || history.page >= pageCount}
                onClick={() => void history.loadHistory(pageCount, history.status)}
                aria-label="Última página"
              >
                <ChevronsRight aria-hidden="true" className="size-4" />
              </Button>
            </div>
          </footer>
        ) : null}
      </Card>
      <p className="hidden shrink-0 text-xs text-muted-foreground sm:block">
        Atualização automática a cada 30 segundos · Horários de Brasília ·
        Totais por envio da loja selecionada · Lista agrupada por oferta
      </p>
    </section>
  );
}
