"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { SelectField } from "@/components/ui/select";
import { useWhatsApp } from "@/features/whatsapp/hooks/use-whatsapp";
import type { DestinationInput, DestinationSummary } from "@/shared/contracts/user-config";
import { PlatformLogo } from "@/components/PlatformLogo";

const statusLabels: Record<string, string> = {
  LOADING: "Consultando conexão…", UNCONFIGURED: "Integração ainda não configurada pelo administrador",
  STOPPED: "Desconectado", STARTING: "Iniciando WhatsApp…", SCAN_QR_CODE: "Escaneie QR para conectar",
  WORKING: "Conectado", FAILED: "Falha de conexão — tente conectar novamente",
  PASSKEY_REQUIRED: "WhatsApp solicitou confirmação adicional. Confira seu celular.",
  PASSKEY_CONFIRMATION_REQUIRED: "Confirme vinculação no seu celular.",
};

type Props = ({
  connectionOnly?: false;
  destinations: DestinationSummary[];
  saveDestination: (input: DestinationInput) => Promise<boolean>;
} | {
  connectionOnly: true;
  destinations?: never;
  saveDestination?: never;
}) & {
  busy?: boolean;
  connectionId?: number;
  onDisconnect: () => void;
  onStatusChange?: (status: string) => void;
};

export function WhatsAppConnection({ destinations = [], saveDestination, connectionOnly = false, busy = false, connectionId, onDisconnect, onStatusChange }: Props) {
  const whatsapp = useWhatsApp({ connectionOnly, connectionId });
  useEffect(() => {
    onStatusChange?.(whatsapp.connection.status);
  }, [onStatusChange, whatsapp.connection.status]);
  const [chatId, setChatId] = useState("");
  const [chatType, setChatType] = useState<"group" | "channel">("channel");
  const [confirmDisconnect, setConfirmDisconnect] = useState(false);
  const disabled = whatsapp.busy || busy;
  const connected = whatsapp.connection.status === "WORKING";
  const chats = chatType === "group" ? whatsapp.groups : whatsapp.channels;
  const chatsError = chatType === "group" ? whatsapp.groupsError : whatsapp.channelsError;
  const availableChats = chats.filter((chat) => !destinations.some((destination) => destination.platform === "whatsapp" && destination.chat_id === chat.id));

  async function disconnect() {
    if (await whatsapp.disconnect()) {
      setConfirmDisconnect(false);
      setChatId("");
      onDisconnect();
    }
  }

  async function addDestination() {
    const chat = chats.find((item) => item.id === chatId);
    if (chat && saveDestination && await saveDestination({ chat_id: chat.id, title: chat.name, chat_type: chatType, enabled: true, platform: "whatsapp", connection_id: connectionId })) {
      setChatId("");
    }
  }

  return <div className="space-y-4">
    <p aria-live="polite" className="flex items-center gap-2"><PlatformLogo platform="whatsapp" />{statusLabels[whatsapp.connection.status] ?? whatsapp.connection.status}{whatsapp.connection.name ? ` · ${whatsapp.connection.name}` : ""}</p>
    {whatsapp.error ? <p role="alert" className="text-sm text-destructive">{whatsapp.error}</p> : null}
    {whatsapp.error ? <Button variant="outline" disabled={disabled} onClick={() => void whatsapp.refresh()}>Tentar novamente</Button> : null}
    {["STOPPED", "FAILED"].includes(whatsapp.connection.status) ? <Button disabled={disabled} onClick={() => void whatsapp.start()}>Conectar WhatsApp</Button> : null}
    {whatsapp.qr ? <div className="space-y-3"><p className="text-sm">No celular: WhatsApp → Aparelhos conectados → Conectar aparelho. QR atualizado automaticamente.</p><Image src={whatsapp.qr} unoptimized width={256} height={256} alt="QR para conectar sua conta WhatsApp" className="rounded-lg bg-white p-2" /></div> : null}
    {connected ? <div className="space-y-3">
      <div className="flex flex-wrap gap-2">{!connectionOnly ? <Button variant="outline" disabled={disabled} onClick={() => void whatsapp.loadGroups()}>Atualizar destinos</Button> : null}<Button variant="outline" disabled={disabled} onClick={() => setConfirmDisconnect(true)}>Desconectar conta</Button></div>
      {!connectionOnly ? <><div className="space-y-2">
        <label className="block text-sm font-medium" htmlFor="whatsapp-chat-type">
          Tipo de destino
        </label>
        <SelectField
          id="whatsapp-chat-type"
          value={chatType}
          disabled={disabled}
          options={[
            { value: "group", label: "Grupo" },
            { value: "channel", label: "Canal" },
          ]}
          onValueChange={(value) => {
            setChatType(value as "group" | "channel");
            setChatId("");
          }}
        />
      </div>
      {chatsError ? <p role="alert" className="text-sm text-destructive">{chatsError}</p> : null}
      <div className="space-y-2">
        <label className="block text-sm font-medium" htmlFor="whatsapp-chat-id">
          {chatType === "group" ? "Grupo de destino" : "Canal de destino"}
        </label>
        <SelectField
          id="whatsapp-chat-id"
          value={chatId}
          disabled={disabled}
          options={[
            { value: "", label: `Selecione ${chatType === "group" ? "um grupo" : "um canal"}` },
            ...availableChats.map((chat) => ({ value: chat.id, label: chat.name })),
          ]}
          onValueChange={setChatId}
        />
      </div>
      {!chatsError && !availableChats.length ? <p className="text-sm text-muted-foreground">Nenhum {chatType === "group" ? "grupo" : "canal administrado"} disponível para adicionar. Confira sua conta e atualize os destinos; destinos já cadastrados não aparecem novamente.</p> : null}
      <Button disabled={disabled || !availableChats.some((chat) => chat.id === chatId)} onClick={() => void addDestination()}>Adicionar {chatType === "group" ? "grupo" : "canal"} WhatsApp</Button>
      <p className="text-sm text-muted-foreground">Grupos: sua conta precisa participar e ter permissão para enviar. Canais: só aparecem aqueles que você administra. Publicações serão feitas em nome da conta conectada.</p></> : null}
    </div> : null}
    {confirmDisconnect ? <div className="rounded-lg bg-muted p-3 text-sm"><p>Desconectar WhatsApp? Publicação nos seus grupos e canais será desativada.</p><div className="mt-3 flex gap-2"><Button variant="destructive" disabled={disabled} onClick={() => void disconnect()}>Desconectar</Button><Button variant="outline" onClick={() => setConfirmDisconnect(false)}>Cancelar</Button></div></div> : null}
  </div>;
}
