import {
  CheckCheck,
  ChevronDown,
  CircleAlert,
  Clock3,
  Minus,
} from "lucide-react";
import { DeliveryRow } from "@/features/dashboard/components/DeliveryRow";
import { AffiliateLinkActions } from "@/features/dashboard/components/AffiliateLinkActions";
import {
  deliveryStatusLabels,
  formatDeliveryDate,
  getPlatformLabel,
} from "@/features/dashboard/lib/delivery-presentation";
import type { Publication } from "@/features/dashboard/types";
import { cn } from "@/lib/utils";

export function PublicationRow({ publication }: { publication: Publication }) {
  const { deliveries } = publication;
  const latest = deliveries[0];
  const title =
    deliveries.find((delivery) => delivery.title)?.title ||
    "Promoção sem título registrado";
  const price = deliveries.find((delivery) => delivery.price)?.price;
  const affiliateUrl = deliveries.find((delivery) => delivery.affiliate_url)?.affiliate_url ?? null;
  const sent = deliveries.filter((delivery) => delivery.status === "sent").length;
  const pending = deliveries.filter((delivery) =>
    ["queued", "retrying", "sending"].includes(delivery.status),
  ).length;
  const failures = deliveries.filter((delivery) =>
    ["failed", "uncertain"].includes(delivery.status),
  ).length;
  const destinationCount = new Set(
    deliveries.map((delivery) => delivery.chat_id),
  ).size;
  const isComplete = sent === deliveries.length;
  const hasMixedResults =
    new Set(deliveries.map((delivery) => delivery.status)).size > 1;
  const statusLabel = isComplete
    ? "Publicada"
    : hasMixedResults
      ? sent > 0
        ? "Parcial"
        : pending > 0
          ? "Em andamento"
          : "Não publicada"
      : deliveryStatusLabels[latest.status];
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
        <summary className="grid min-h-16 cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto_16px] items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-muted/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring group-open/publication:bg-muted/50 motion-reduce:transition-none md:min-h-14 md:grid-cols-[minmax(0,1fr)_140px_132px_104px_16px] md:gap-4 md:px-5 md:py-2 xl:grid-cols-[minmax(0,1fr)_104px_160px_132px_104px_16px] [&::-webkit-details-marker]:hidden">
          <span className="min-w-0">
            <span className="block truncate font-medium" title={title}>
              {title}
            </span>
            <span
              className={cn(
                "mt-1 block truncate text-xs tabular-nums",
                price ? "font-semibold text-foreground" : "text-muted-foreground",
              )}
              title={price || "Preço não registrado"}
              aria-label={`Preço anunciado: ${price || "não registrado"}`}
            >
              {price || "Preço não registrado"}
            </span>
            <span className="mt-1 block text-xs text-muted-foreground md:hidden">
              {sent}/{deliveries.length} envios confirmados · {destinationCount} {destinationCount === 1 ? "destino" : "destinos"}
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
            <span className="mt-0.5 block">{sent}/{deliveries.length} envios confirmados</span>
          </span>
          <span
            className={cn(
              "inline-flex w-fit items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-medium whitespace-nowrap",
              isComplete
                ? "border-sidebar-primary/20 bg-sidebar-primary/10 text-foreground"
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
          <h3 className="wrap-anywhere text-sm/relaxed font-medium">{title}</h3>
          <p className="mt-1 wrap-anywhere text-sm font-semibold tabular-nums">
            Preço anunciado: {price || "não registrado"}
          </p>
          <AffiliateLinkActions key={affiliateUrl} url={affiliateUrl} />
          <p className="mt-1 text-xs/relaxed text-muted-foreground">
            Resultado por grupo ou canal. Abra um destino para ver tentativas e detalhes do envio.
          </p>
          <ul className="mt-3 divide-y overflow-hidden rounded-xl border bg-card" aria-label={`Destinos de ${title}`}>
            {deliveries.map((delivery) => (
              <DeliveryRow key={delivery.id} delivery={delivery} />
            ))}
          </ul>
        </div>
      </details>
    </li>
  );
}
