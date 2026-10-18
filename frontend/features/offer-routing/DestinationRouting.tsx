"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { OfferCategorySelector } from "@/features/offer-routing/OfferCategorySelector";
import type { DestinationInput, DestinationSummary, OfferCategory } from "@/shared/contracts/user-config";

type SaveDestination = (input: DestinationInput, id: number) => Promise<boolean>;

function DestinationRule({ destination, saveDestination, disabled }: {
  destination: DestinationSummary;
  saveDestination: SaveDestination;
  disabled: boolean;
}) {
  const [categories, setCategories] = useState<OfferCategory[] | null>(destination.categories ?? null);
  const changed = JSON.stringify(categories) !== JSON.stringify(destination.categories ?? null);
  return (
    <li className="space-y-3 rounded-xl border p-4">
      <div>
        <h4 className="wrap-anywhere font-medium">{destination.title || destination.chat_id}</h4>
        <p className="text-xs text-muted-foreground">
          {destination.platform === "whatsapp" ? "WhatsApp" : "Telegram"} · {destination.chat_type === "channel" ? "Canal" : "Grupo"} · {destination.enabled ? "Habilitado" : "Desativado"}
        </p>
      </div>
      <OfferCategorySelector value={categories} onChange={setCategories} disabled={disabled} />
      <Button
        variant="outline"
        disabled={disabled || !changed}
        onClick={() => void saveDestination({
          chat_id: destination.chat_id,
          title: destination.title ?? null,
          chat_type: destination.chat_type ?? "group",
          platform: destination.platform ?? "telegram",
          enabled: destination.enabled,
          categories,
        }, destination.id)}
      >
        Salvar categorias
      </Button>
    </li>
  );
}

export function DestinationRouting({ destinations, saveDestination, disabled = false }: {
  destinations: DestinationSummary[];
  saveDestination: SaveDestination;
  disabled?: boolean;
}) {
  return (
    <section className="space-y-4 rounded-xl border bg-card p-5 sm:p-6" aria-label="Categorias por destino">
      <div>
        <h3 className="font-semibold">Categorias por grupo ou canal</h3>
        <p className="mt-2 text-sm/relaxed text-muted-foreground">
          Telegram e WhatsApp: envie tudo para um destino e selecione categorias específicas para outros.
          Cada destino tem regras independentes. Alterações valem também para ofertas ainda aguardando envio.
        </p>
      </div>
      {destinations.length ? (
        <ul className="grid gap-4 lg:grid-cols-2">
          {destinations.map((destination) => (
            <DestinationRule
              key={`${destination.id}:${JSON.stringify(destination.categories ?? null)}`}
              destination={destination}
              saveDestination={saveDestination}
              disabled={disabled}
            />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">Adicione grupos ou canais do Telegram ou WhatsApp para escolher as categorias.</p>
      )}
    </section>
  );
}
