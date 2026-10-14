"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SettingsState } from "@/features/settings/hooks/use-settings";
import { WhatsAppConnection } from "@/features/whatsapp/WhatsAppConnection";

export function WhatsAppSettings({ settings }: { settings: SettingsState }) {
  const [removingId, setRemovingId] = useState<number | null>(null);
  const destinations = settings.destinations.filter((destination) => destination.platform === "whatsapp");
  const disabled = Boolean(settings.busy);

  return <Card id="whatsapp" className="scroll-mt-6">
    <CardHeader><CardTitle>Publicar no WhatsApp</CardTitle><p className="text-sm/6 text-muted-foreground">Conecte sua conta e escolha grupos ou canais onde deseja receber ofertas com seus links de afiliado.</p></CardHeader>
    <CardContent className="space-y-4">
      <WhatsAppConnection destinations={destinations} saveDestination={settings.saveDestination} busy={disabled} />
      <ul className="divide-y divide-border">{destinations.map((destination) => <li key={destination.id} className="space-y-3 py-3"><p className="font-medium">{destination.title || destination.chat_id} · {destination.chat_type === "channel" ? "Canal" : "Grupo"} · {destination.enabled ? "Habilitado" : "Desativado"}</p><div className="flex gap-2"><Button variant="outline" disabled={disabled} onClick={() => void settings.toggleDestination(destination)}>{destination.enabled ? "Desativar" : "Habilitar"}</Button><Button variant="outline" disabled={disabled} onClick={() => setRemovingId(destination.id)}>Remover</Button></div>{removingId === destination.id ? <div className="flex gap-2"><Button variant="destructive" disabled={disabled} onClick={async () => { if (await settings.removeDestination(destination.id)) setRemovingId(null); }}>Confirmar remoção</Button><Button variant="outline" onClick={() => setRemovingId(null)}>Cancelar</Button></div> : null}</li>)}</ul>
    </CardContent>
  </Card>;
}
