"use client";

import { Zap } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { SelectField } from "@/components/ui/select";
import { useManualPublication } from "@/features/dashboard/hooks/use-manual-publication";
import { getPlatformLabel } from "@/features/dashboard/lib/delivery-presentation";
import type { DestinationSummary } from "@/shared/contracts/user-config";

export function ManualPostAction({
  deliveryId,
  destinations,
  handledChatIds,
  onPosted,
}: {
  deliveryId: string;
  destinations: DestinationSummary[];
  handledChatIds: Set<string>;
  onPosted: () => void;
}) {
  const [selected, setSelected] = useState("");
  const { isPublishing, error, lastPostedChatId, publish } =
    useManualPublication(onPosted);

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

  if (!available.length) {
    return null;
  }

  const options = available.map((destination) => ({
    value: destination.chat_id,
    label: `${destination.title || destination.chat_id} · ${getPlatformLabel(destination.platform ?? null)}`,
  }));
  const value = options.some((option) => option.value === selected)
    ? selected
    : options[0].value;

  return (
    <div className="mt-4 rounded-xl border bg-background p-3">
      <p className="text-sm font-medium">Publicar em outro destino</p>
      <p className="mt-1 text-xs/relaxed text-muted-foreground">
        Envia imediatamente, ignorando limites de frequência, rajada e janela de
        publicação.
      </p>
      <div className="mt-3 flex flex-col gap-2 sm:flex-row">
        <div className="min-w-0 flex-1">
          <label htmlFor={`manual-destination-${deliveryId}`} className="sr-only">
            Destino da publicação manual
          </label>
          <SelectField
            id={`manual-destination-${deliveryId}`}
            value={value}
            options={options}
            disabled={isPublishing}
            onValueChange={setSelected}
          />
        </div>
        <Button
          type="button"
          className="min-h-11 sm:w-auto"
          disabled={isPublishing}
          onClick={() => void publish(deliveryId, value)}
        >
          <Zap aria-hidden="true" />
          {isPublishing ? "Publicando…" : "Publicar agora"}
        </Button>
      </div>
      {error ? (
        <p role="alert" className="mt-2 text-xs text-destructive">
          {error}
        </p>
      ) : null}
      {lastPostedChatId ? (
        <p role="status" className="mt-2 text-xs text-muted-foreground">
          Publicação enfileirada. O resultado aparece em instantes.
        </p>
      ) : null}
    </div>
  );
}
