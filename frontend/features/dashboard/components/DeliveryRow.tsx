import {
  Check,
  ChevronDown,
  CircleAlert,
  Clock3,
  MessageCircle,
  Minus,
  Send,
} from "lucide-react";
import {
  deliveryStatusLabels,
  formatDeliveryDate,
  getDeliveryStage,
  getPlatformLabel,
} from "@/features/dashboard/lib/delivery-presentation";
import type { Delivery } from "@/features/dashboard/types";
import { cn } from "@/lib/utils";

export function DeliveryRow({ delivery }: { delivery: Delivery }) {
  const title = delivery.title || "Promoção sem título registrado";
  const destination = delivery.destination_title || delivery.chat_id;
  const isFailure =
    delivery.status === "failed" || delivery.status === "uncertain";
  const isPending = ["queued", "retrying", "sending"].includes(delivery.status);
  const StatusIcon =
    delivery.status === "sent"
      ? Check
      : isFailure
        ? CircleAlert
        : isPending
          ? Clock3
          : Minus;
  const destinationPlatform =
    delivery.chat_id.endsWith("@newsletter") ||
    delivery.chat_id.endsWith("@g.us")
      ? "WhatsApp"
      : "Telegram";
  const DestinationIcon =
    destinationPlatform === "WhatsApp" ? MessageCircle : Send;
  const details = [
    { label: "Loja", value: getPlatformLabel(delivery.platform) },
    { label: "Preço anunciado", value: delivery.price || "Não registrado" },
    { label: "Destino", value: `${destinationPlatform} · ${destination}` },
    { label: "Etapa", value: getDeliveryStage(delivery) },
    {
      label: "Tentativas",
      value:
        delivery.attempts === 0
          ? "Envio não iniciado"
          : String(delivery.attempts),
    },
    { label: "Registrada em", value: formatDeliveryDate(delivery.created_at) },
    {
      label: "Última atualização",
      value: formatDeliveryDate(delivery.updated_at),
    },
  ];

  return (
    <li>
      <details className="group/delivery">
        <summary className="grid min-h-16 cursor-pointer list-none grid-cols-[minmax(0,1fr)_auto_16px] items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-muted/50 focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ring group-open/delivery:bg-muted/50 motion-reduce:transition-none md:min-h-14 md:grid-cols-[minmax(0,1fr)_132px_104px_16px] md:gap-4 [&::-webkit-details-marker]:hidden">
          <span className="min-w-0">
            <span className="flex items-center gap-2 font-medium" title={destination}>
              <DestinationIcon aria-hidden="true" className="size-3.5 shrink-0 text-muted-foreground" />
              <span className="truncate">{destination}</span>
            </span>
            <span className="mt-1 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
              <span className="truncate">
                {destinationPlatform}
              </span>
              <span aria-hidden="true" className="md:hidden">·</span>
              <time
                className="shrink-0 tabular-nums md:hidden"
                dateTime={delivery.created_at}
              >
                {formatDeliveryDate(delivery.created_at, true)}
              </time>
            </span>
          </span>
          <span
            className={cn(
              "inline-flex w-fit max-w-36 items-center gap-1.5 rounded-full border px-2 py-1 text-xs font-medium whitespace-nowrap",
              delivery.status === "sent"
                ? "border-sidebar-primary/20 bg-sidebar-primary/10 text-foreground"
                : isFailure
                  ? "border-destructive/20 bg-background text-destructive"
                  : "border-border bg-muted/50 text-muted-foreground",
            )}
          >
            <StatusIcon aria-hidden="true" className="size-3.5 shrink-0" />
            {deliveryStatusLabels[delivery.status]}
          </span>
          <time
            dateTime={delivery.created_at}
            title={formatDeliveryDate(delivery.created_at)}
            className="hidden whitespace-nowrap text-xs text-muted-foreground tabular-nums md:block"
          >
            {formatDeliveryDate(delivery.created_at, true)}
          </time>
          <ChevronDown
            aria-hidden="true"
            className="size-4 text-muted-foreground transition-transform group-open/delivery:rotate-180 motion-reduce:transition-none"
          />
        </summary>
        <div className="border-t border-dashed bg-muted/20 px-4 py-5 md:px-5">
          <h3 className="wrap-anywhere text-sm/relaxed font-medium">{title}</h3>
          {delivery.reason_message ? (
            <p
              className={cn(
                "mt-3 flex items-start gap-2 rounded-xl border p-3 text-sm/relaxed",
                isFailure
                  ? "border-destructive/20 bg-destructive/5"
                  : "border-border bg-background",
              )}
            >
              <CircleAlert
                aria-hidden="true"
                className={cn(
                  "mt-0.5 size-4 shrink-0",
                  isFailure ? "text-destructive" : "text-muted-foreground",
                )}
              />
              <span className="min-w-0 wrap-anywhere">
                {delivery.reason_message}
              </span>
            </p>
          ) : null}
          <dl className="mt-4 grid gap-x-6 gap-y-4 sm:grid-cols-2 xl:grid-cols-3">
            {details.map((detail) => (
              <div className="min-w-0" key={detail.label}>
                <dt className="text-xs text-muted-foreground">
                  {detail.label}
                </dt>
                <dd className="mt-1 wrap-anywhere text-sm">{detail.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </details>
    </li>
  );
}
