"use client";

import { useState } from "react";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { useWhatsApp } from "@/features/whatsapp/hooks/use-whatsapp";
import type { DestinationInput, DestinationSummary } from "@/shared/contracts/user-config";

const statusLabels: Record<string, string> = {
  LOADING: "Consultando conexão…", UNCONFIGURED: "Integração ainda não configurada pelo administrador",
  STOPPED: "Desconectado", STARTING: "Iniciando WhatsApp…", SCAN_QR_CODE: "Escaneie QR para conectar",
  WORKING: "Conectado", FAILED: "Falha de conexão — tente conectar novamente",
  PASSKEY_REQUIRED: "WhatsApp solicitou confirmação adicional. Confira seu celular.",
  PASSKEY_CONFIRMATION_REQUIRED: "Confirme vinculação no seu celular.",
};

type Props = {
  destinations: DestinationSummary[];
  saveDestination: (input: DestinationInput) => Promise<boolean>;
  busy?: boolean;
};

export function WhatsAppConnection({ destinations, saveDestination, busy = false }: Props) {
  const whatsapp = useWhatsApp();
  const [chatId, setChatId] = useState("");
  const [chatType, setChatType] = useState<"group" | "channel">("group");
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const disabled = whatsapp.busy || busy;
  const connected = whatsapp.connection.status === "WORKING";
  const chats = chatType === "group" ? whatsapp.groups : whatsapp.channels;

  async function disconnect() {
    if (await whatsapp.disconnect()) window.location.reload();
  }

  async function addDestination() {
    const chat = chats.find((item) => item.id === chatId);
    if (chat && await saveDestination({ chat_id: chat.id, title: chat.name, chat_type: chatType, enabled: true, platform: "whatsapp" })) setChatId("");
  }

  return <div className="space-y-4">
    <p aria-live="polite">{statusLabels[whatsapp.connection.status] ?? whatsapp.connection.status}{whatsapp.connection.name ? ` · ${whatsapp.connection.name}` : ""}</p>
    {whatsapp.error ? <p role="alert" className="text-sm text-destructive">{whatsapp.error}</p> : null}
    {["STOPPED", "FAILED"].includes(whatsapp.connection.status) ? <Button disabled={disabled} onClick={() => void whatsapp.start()}>Conectar WhatsApp</Button> : null}
    {whatsapp.qr ? <div className="space-y-3"><p className="text-sm">No celular: WhatsApp → Aparelhos conectados → Conectar aparelho. QR atualizado automaticamente.</p><Image src={whatsapp.qr} unoptimized width={256} height={256} alt="QR para conectar sua conta WhatsApp" className="rounded-lg bg-white p-2" /></div> : null}
    {connected ? <div className="space-y-3">
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={disabled} onClick={() => void whatsapp.loadGroups()}>Atualizar destinos</Button><Button variant="outline" disabled={disabled} onClick={() => setConfirmDisconnect(true)}>Desconectar conta</Button></div>
      <label className="block space-y-2 text-sm font-medium">Tipo de destino<select className="h-11 w-full rounded-lg border border-border bg-background px-3" value={chatType} disabled={disabled} onChange={(event) => { setChatType(event.target.value as "group" | "channel"); setChatId(""); }}><option value="group">Grupo</option><option value="channel">Canal</option></select></label>
      {chatType === "channel" && whatsapp.channelsError ? <p role="alert" className="text-sm text-destructive">{whatsapp.channelsError}</p> : null}
      <label className="block space-y-2 text-sm font-medium">{chatType === "group" ? "Grupo de destino" : "Canal de destino"}<select className="h-11 w-full rounded-lg border border-border bg-background px-3" value={chatId} disabled={disabled} onChange={(event) => setChatId(event.target.value)}><option value="">Selecione {chatType === "group" ? "um grupo" : "um canal"}</option>{chats.filter((chat) => !destinations.some((destination) => destination.platform === "whatsapp" && destination.chat_id === chat.id)).map((chat) => <option key={chat.id} value={chat.id}>{chat.name}</option>)}</select></label>
      <Button disabled={disabled || !chatId} onClick={() => void addDestination()}>Adicionar {chatType === "group" ? "grupo" : "canal"} WhatsApp</Button>
      <p className="text-sm text-muted-foreground">Grupos: sua conta precisa participar e ter permissão para enviar. Canais: só aparecem aqueles que você administra. Publicações serão feitas em nome da conta conectada.</p>
    </div> : null}
    {confirmDisconnect ? <div className="rounded-lg bg-muted p-3 text-sm"><p>Desconectar WhatsApp? Publicação nos seus grupos e canais será desativada.</p><div className="mt-3 flex gap-2"><Button variant="destructive" disabled={disabled} onClick={() => void disconnect()}>Desconectar</Button><Button variant="outline" onClick={() => setConfirmDisconnect(false)}>Cancelar</Button></div></div> : null}
  </div>;
}
