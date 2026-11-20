"use client";

import { Zap } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SelectField } from "@/components/ui/select";
import { useManualPublication } from "@/features/dashboard/hooks/use-manual-publication";
import { getPlatformLabel } from "@/features/dashboard/lib/delivery-presentation";
import type { Delivery } from "@/features/dashboard/types";
import type { DestinationSummary } from "@/shared/contracts/user-config";

export function ManualPostAction({
  deliveryId,
  destinations,
  handledChatIds,
  deliveries,
  onPosted,
}: {
  deliveryId: string;
  destinations: DestinationSummary[];
  handledChatIds: Set<string>;
  deliveries: Delivery[];
  onPosted: () => void;
}) {
  const [selected, setSelected] = useState("");
  const { isPublishing, error, queuedId, publish } =
    useManualPublication(onPosted);
  const awaitingHistory = queuedId !== null && !deliveries.some(({ id }) => id === queuedId);

  const available = [
    ...new Map(
      destinations
        .filter(
          (destination) =>
            destination.enabled &&
            !handledChatIds.has(destination.chat_id),
        )
        .map((destination) => [destination.chat_id, destination]),
    ).values(),
  ];

  if (awaitingHistory) {
    return (
      <p role="status" className="mt-4 text-sm text-muted-foreground">
        Envio na fila. Acompanhe a confirmação em Envios por canal.
      </p>
    );
  }
  if (!available.length && !error) {
    return null;
  }

  const destinationsOptions = available.map((destination) => ({
    value: destination.chat_id,
    label: `${destination.title || destination.chat_id} · ${getPlatformLabel(destination.platform ?? null)}`,
  }));
  const value = destinationsOptions.some((option) => option.value === selected)
    ? selected
    : "";

  return (
    <div className="mt-4 rounded-xl border bg-background p-3">
      <p className="text-sm font-medium">Publicar em um destino</p>
      <p className="mt-1 text-xs/relaxed text-muted-foreground">
        Coloca o envio na fila sem aguardar a janela de publicação ou os limites de frequência.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <div className="min-w-0 flex-1">
          <label htmlFor={`manual-destination-${deliveryId}`} className="sr-only">
            Destino da publicação manual
          </label>
          <SelectField
            id={`manual-destination-${deliveryId}`}
            value={value}
            options={[{ value: "", label: "Selecione um destino" }, ...destinationsOptions]}
            disabled={isPublishing || !available.length}
            onValueChange={setSelected}
          />
        </div>
        <Button
          type="button"
          className="min-h-11 sm:w-auto"
          disabled={isPublishing || !value}
          onClick={async () => {
            if (await publish(deliveryId, value)) setSelected("");
          }}
        >
          <Zap aria-hidden="true" />
          {isPublishing ? "Enfileirando…" : "Publicar agora"}
        </Button>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
