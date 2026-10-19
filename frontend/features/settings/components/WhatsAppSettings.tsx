"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SettingsState } from "@/features/settings/hooks/use-settings";
import { WhatsAppConnection } from "@/features/whatsapp/WhatsAppConnection";
import { WhatsAppDeliveryControls } from "@/features/whatsapp/WhatsAppDeliveryControls";
import { PlatformLogo } from "@/components/PlatformLogo";

export function WhatsAppSettings({ settings }: { settings: SettingsState }) {
  const [removingId, setRemovingId] = useState<number | null>(null);
  const destinations = settings.destinations.filter(
    (destination) => destination.platform === "whatsapp",
  );
  const disabled = Boolean(settings.busy);

  return (
    <Card id="whatsapp" className="scroll-mt-32 gap-0 overflow-hidden py-0">
      <CardHeader className="border-b p-5 sm:p-6">
        <CardTitle className="flex items-center gap-2">
          <PlatformLogo platform="whatsapp" />
          WhatsApp
        </CardTitle>
        <p className="max-w-prose text-sm/6 text-muted-foreground">
          Conecte sua conta e escolha grupos ou canais onde deseja receber
          ofertas com seus links de afiliado.
        </p>
        <Link href="/whatsapp" className="text-sm font-medium text-primary underline underline-offset-4">Gerenciar grupos, lotação e categorias →</Link>
      </CardHeader>
      <CardContent className="grid gap-6 p-5 sm:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,400px)]">
        <section className="min-w-0" aria-label="Destinos do WhatsApp">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Seus destinos</h3>
            <span className="text-xs text-muted-foreground">{destinations.length} cadastrados</span>
          </div>
          {!destinations.length ? (
            <div className="rounded-xl border border-dashed p-6">
              <p className="text-sm font-medium">Nenhum destino cadastrado</p>
              <p className="mt-2 text-sm/6 text-muted-foreground">Conecte sua conta e adicione um grupo ou canal do WhatsApp.</p>
            </div>
          ) : null}
          <ul className="divide-y rounded-xl border px-4 empty:hidden">
            {destinations.map((destination) => (
              <li key={destination.id} className="space-y-3 py-4">
                <p className="flex items-center gap-2 font-medium">
                  <PlatformLogo platform="whatsapp" />
                  <span className="min-w-0 wrap-anywhere">{destination.title || destination.chat_id}</span>
                </p>
                <p className="wrap-anywhere text-xs text-muted-foreground">
                  {destination.chat_type === "channel" ? "Canal" : "Grupo"} ·{" "}
                  {destination.enabled ? "Habilitado" : "Desativado"} · {destination.chat_id}
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    disabled={disabled}
                    onClick={() => void settings.toggleDestination(destination)}
                  >
                    {destination.enabled ? "Desativar" : "Habilitar"}
                  </Button>
                  <Button
                    variant="ghost"
                    disabled={disabled}
                    onClick={() => setRemovingId(destination.id)}
                  >
                    Remover
                  </Button>
                </div>
                {removingId === destination.id ? (
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="destructive"
                      disabled={disabled}
                      onClick={async () => {
                        if (await settings.removeDestination(destination.id))
                          setRemovingId(null);
                      }}
                    >
                      Confirmar remoção
                    </Button>
                    <Button variant="outline" disabled={disabled} onClick={() => setRemovingId(null)}>
                      Cancelar
                    </Button>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
        <section className="min-w-0 space-y-4 rounded-xl border bg-muted/20 p-4 sm:p-5" aria-label="Conexão e novo destino WhatsApp">
          <h3 className="text-sm font-semibold">Conectar e adicionar destino</h3>
          <WhatsAppConnection
            destinations={destinations}
            saveDestination={settings.saveDestination}
            busy={disabled}
            onDisconnect={settings.handleWhatsAppDisconnect}
          />
        </section>
        <div className="min-w-0 xl:col-span-2"><WhatsAppDeliveryControls /></div>
      </CardContent>
    </Card>
  );
}
