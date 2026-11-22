import {
  CheckCheck,
  ChevronDown,
  CircleAlert,
  Clock3,
  Minus,
} from "lucide-react";
import { DeliveryRow } from "@/features/dashboard/components/DeliveryRow";
import { AffiliateLinkActions } from "@/features/dashboard/components/AffiliateLinkActions";
import { ManualPostAction } from "@/features/dashboard/components/ManualPostAction";
import {
  deliveryStatusLabels,
  formatDeliveryDate,
  getPlatformLabel,
} from "@/features/dashboard/lib/delivery-presentation";
import type { Publication } from "@/features/dashboard/types";
import type { DestinationSummary } from "@/shared/contracts/user-config";
import { cn } from "@/lib/utils";

export function PublicationRow({
  publication,
  destinations,
  onPosted,
}: {
  publication: Publication;
  destinations: DestinationSummary[];
  onPosted: () => void;
}) {
  const { deliveries } = publication;
  const latest = deliveries[0];
  const queueTimes = deliveries.flatMap(({ enqueue_ms }) => enqueue_ms == null ? [] : [enqueue_ms]);
  const enqueueMs = queueTimes.length ? Math.min(...queueTimes) : null;
  const title =
    deliveries.find((delivery) => delivery.title)?.title ||
    "Promoção sem título registrado";
  const price = deliveries.find((delivery) => delivery.price)?.price;
  const coupon = deliveries.find((delivery) => delivery.coupon?.trim())?.coupon?.trim();
  const affiliateUrl = deliveries.find((delivery) => delivery.affiliate_url)?.affiliate_url ?? null;
  // History is newest first. A confirmed post remains confirmed even if a later
  // record for the same destination was unsuccessful.
  const byDestination = new Map<string, Publication["deliveries"]>();
  for (const delivery of deliveries) {
    const records = byDestination.get(delivery.chat_id);
    if (records) records.push(delivery);
    else byDestination.set(delivery.chat_id, [delivery]);
  }
  const destinationsWithHistory = [...byDestination.values()].map((records) => {
    const current = records.find((record) => record.status === "sent") ?? records[0];
    return { current, previous: records.filter((record) => record.id !== current.id) };
  });
  const currentDeliveries = destinationsWithHistory.map(({ current }) => current);
  const sent = currentDeliveries.filter((delivery) => delivery.status === "sent").length;
  const pending = currentDeliveries.filter((delivery) =>
    ["queued", "retrying", "sending"].includes(delivery.status),
  ).length;
  const failures = currentDeliveries.filter((delivery) =>
    ["failed", "uncertain"].includes(delivery.status),
  ).length;
  const destinationCount = currentDeliveries.length;
  const handledChatIds = new Set(
    deliveries
      .filter((delivery) =>
        ["queued", "retrying", "sending", "sent", "uncertain"].includes(
          delivery.status,
        ),
      )
      .map((delivery) => delivery.chat_id),
  );
  const isComplete = sent === destinationCount;
  const hasMixedResults =
    new Set(currentDeliveries.map((delivery) => delivery.status)).size > 1;
  const statusLabel = isComplete
    ? "Publicada"
    : hasMixedResults
      ? sent > 0
        ? "Parcial"
        : pending > 0
          ? "Em andamento"
          : "Não publicada"
      : deliveryStatusLabels[currentDeliveries[0].status];
  const StatusIcon = isComplete
    ? CheckCheck
    : failures > 0
      ? CircleAlert
      : pending > 0
        ? Clock3
        : Minus;

  return (
    <li>
      <details className="group/publication">
        <summary className="grid min-h-16 cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto_16px] items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-muted/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring group-open/publication:bg-primary/10 group-open/publication:inset-ring-1 group-open/publication:inset-ring-primary/30 motion-reduce:transition-none md:min-h-14 md:grid-cols-[minmax(0,1fr)_140px_132px_104px_16px] md:gap-4 md:px-5 md:py-2 xl:grid-cols-[minmax(0,1fr)_104px_160px_132px_104px_16px] [&::-webkit-details-marker]:hidden">
          <span className="min-w-0">
            <span className="block truncate font-medium group-open/publication:whitespace-normal group-open/publication:wrap-anywhere" title={title}>
              {title}
            </span>
            <span className="mt-1 flex flex-wrap items-baseline gap-x-3 gap-y-1 text-xs tabular-nums">
              <span
                className={cn("min-w-0 wrap-anywhere", price ? "font-semibold text-foreground" : "text-muted-foreground")}
                title={price || "Preço não registrado"}
                aria-label={`Preço anunciado: ${price || "não registrado"}`}
              >
                {price || "Preço não registrado"}
              </span>
              {coupon ? <span className="min-w-0 wrap-anywhere font-semibold text-primary dark:text-sidebar-primary">CUPOM: {coupon}</span> : null}
              {enqueueMs !== null && <span className="text-muted-foreground" title="Do recebimento no Telegram até a entrada no primeiro destino da fila">{enqueueMs < 1000 ? `${enqueueMs} ms` : `${(enqueueMs / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} s`} até a fila</span>}
            </span>
            <span className="mt-1 block text-xs text-muted-foreground md:hidden">
              {sent}/{destinationCount} envios confirmados · {destinationCount} {destinationCount === 1 ? "destino" : "destinos"}
            </span>
          </span>
          <span
            className="hidden truncate text-muted-foreground xl:block"
            title={getPlatformLabel(latest.platform)}
          >
            {getPlatformLabel(latest.platform)}
          </span>
          <span className="hidden text-xs text-muted-foreground md:block">
            <span className="block text-foreground">{destinationCount} {destinationCount === 1 ? "destino" : "destinos"}</span>
            <span className="mt-0.5 block">{sent}/{destinationCount} envios confirmados</span>
          </span>
          <span
            className={cn(
              "inline-flex w-fit items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-medium whitespace-nowrap",
              isComplete
                ? "border-primary bg-primary text-primary-foreground"
                : failures > 0
                  ? "border-destructive/20 bg-background text-destructive"
                  : "border-border bg-muted/50 text-muted-foreground",
            )}
          >
            <StatusIcon aria-hidden="true" className="size-3.5 shrink-0" />
            {statusLabel}
          </span>
          <time
            dateTime={latest.created_at}
            title={formatDeliveryDate(latest.created_at)}
            className="hidden whitespace-nowrap text-xs text-muted-foreground tabular-nums md:block"
          >
            {formatDeliveryDate(latest.created_at, true)}
          </time>
          <ChevronDown
            aria-hidden="true"
            className="size-4 text-muted-foreground transition-transform group-open/publication:rotate-180 motion-reduce:transition-none"
          />
        </summary>
        <div className="border-t border-dashed bg-muted/20 px-3 py-4 sm:px-5">
          <h3 className="text-sm font-medium">Envios por canal</h3>
          <ul className="mt-2 divide-y overflow-hidden rounded-xl border bg-card" aria-label="Envios por canal">
            {destinationsWithHistory.map(({ current, previous }) => (
              <DeliveryRow key={current.chat_id} delivery={current} previous={previous} />
            ))}
          </ul>
          <AffiliateLinkActions key={affiliateUrl} url={affiliateUrl} />
          <ManualPostAction
            deliveryId={deliveries.find((delivery) => delivery.affiliate_url)?.id ?? latest.id}
            destinations={destinations}
            handledChatIds={handledChatIds}
            deliveries={deliveries}
            onPosted={onPosted}
          />
        </div>
      </details>
    </li>
  );
}
