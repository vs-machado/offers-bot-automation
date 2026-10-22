"use client";

import { useState, type FormEvent } from "react";
import { Pencil, Power, PowerOff, Save, Trash2, X } from "lucide-react";
import { PlatformLogo } from "@/components/PlatformLogo";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SelectField } from "@/components/ui/select";
import type { SettingsState } from "@/features/settings/hooks/use-settings";
import type { DestinationSummary } from "@/shared/contracts/user-config";

export function DestinationSettings({ settings }: { settings: SettingsState }) {
  const [editingId, setEditingId] = useState<number | undefined>();
  const [chatId, setChatId] = useState("");
  const [title, setTitle] = useState("");
  const [chatType, setChatType] = useState("group");
  const [enabled, setEnabled] = useState(true);
  const [removingId, setRemovingId] = useState<number | null>(null);
  const disabled = Boolean(settings.busy);
  function reset() {
    setEditingId(undefined);
    setChatId("");
    setTitle("");
    setChatType("group");
    setEnabled(true);
  }
  function edit(destination: DestinationSummary) {
    setEditingId(destination.id);
    setChatId(destination.chat_id);
    setTitle(destination.title ?? "");
    setChatType(destination.chat_type ?? "group");
    setEnabled(destination.enabled);
    document
      .getElementById("destination-form")
      ?.scrollIntoView({ block: "start" });
    document
      .getElementById("destination-chat-id")
      ?.focus({ preventScroll: true });
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (
      await settings.saveDestination(
        {
          chat_id: chatId.trim(),
          title: title.trim() || null,
          chat_type: chatType,
          enabled,
          categories: settings.destinations.find((destination) => destination.id === editingId)?.categories ?? null,
        },
        editingId,
      )
    )
      reset();
  }
  async function remove(id: number) {
    if (await settings.removeDestination(id)) {
      setRemovingId(null);
      if (editingId === id) reset();
    }
  }
  const inputClass =
    "h-11 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50";
  return (
    <Card id="destinations" className="scroll-mt-24 gap-0 overflow-hidden py-0">
      <CardHeader className="border-b p-5 sm:p-6">
        <CardTitle className="flex items-center gap-2">
          <PlatformLogo platform="telegram" />
          Telegram
        </CardTitle>
        <p className="max-w-prose text-sm/6 text-muted-foreground">
          Adicione @tgtestoffersbot como administrador, com permissão para
          enviar mensagens e fotos. Verificamos o acesso ao habilitar cada
          destino.
        </p>
      </CardHeader>
      <CardContent className="grid gap-6 p-5 sm:p-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,400px)]">
        <section className="min-w-0" aria-label="Destinos do Telegram">
          <div className="mb-4 flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold">Seus destinos</h3>
            <span className="text-xs text-muted-foreground">
              {settings.destinations.length} cadastrados
            </span>
          </div>
          {settings.destinations.length ? (
            <ul className="divide-y rounded-xl border px-4">
              {settings.destinations.map((destination) => (
                <li key={destination.id} className="space-y-3 py-4">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 font-medium">
                      <PlatformLogo platform="telegram" />
                      <span className="min-w-0 wrap-anywhere">{destination.title || "Destino do Telegram"}</span>
                    </p>
                    <p className="mt-1 wrap-anywhere text-xs text-muted-foreground">
                      {destination.chat_type === "channel" ? "Canal" : "Grupo"}{" "}
                      · {destination.enabled ? "Habilitado" : "Desativado"} ·{" "}
                      {destination.chat_id}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      disabled={disabled}
                      onClick={() => edit(destination)}
                    >
                      <Pencil aria-hidden="true" />Editar
                    </Button>
                    <Button
                      variant="outline"
                      disabled={disabled}
                      onClick={() =>
                        void settings.toggleDestination(destination)
                      }
                    >
                      {destination.enabled ? <PowerOff aria-hidden="true" /> : <Power aria-hidden="true" />}
                      {destination.enabled ? "Desativar" : "Habilitar"}
                    </Button>
                    <Button
                      variant="destructive-outline"
                      disabled={disabled}
                      onClick={() => setRemovingId(destination.id)}
                    >
                      <Trash2 aria-hidden="true" />Remover
                    </Button>
                  </div>
                  {removingId === destination.id ? (
                    <div className="rounded-lg border bg-muted p-3 text-sm">
                      <p>
                        Remover esse destino? O bot deixará de publicar nele.
                      </p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <Button
                          variant="destructive-outline"
                          disabled={disabled}
                          onClick={() => void remove(destination.id)}
                        >
                          <Trash2 aria-hidden="true" />Confirmar remoção
                        </Button>
                        <Button
                          variant="outline"
                          disabled={disabled}
                          onClick={() => setRemovingId(null)}
                        >
                          <X aria-hidden="true" />Cancelar
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <div className="rounded-xl border border-dashed p-6">
              <p className="text-sm font-medium">Nenhum destino cadastrado</p>
              <p className="mt-2 text-sm/6 text-muted-foreground">
                Adicione um grupo ou canal para começar a publicar suas ofertas
                no Telegram.
              </p>
            </div>
          )}
        </section>
        <form
          id="destination-form"
          onSubmit={submit}
          className="min-w-0 scroll-mt-24 space-y-4 rounded-xl border bg-muted/20 p-4 sm:p-5"
        >
          <h3 className="text-sm font-semibold">
            {editingId ? "Editar destino" : "Adicionar destino"}
          </h3>
          <fieldset disabled={disabled} className="space-y-4">
            <label
              className="block space-y-2 text-sm font-medium"
              htmlFor="destination-chat-id"
            >
              <span>ID do grupo ou canal</span>
              <input
                id="destination-chat-id"
                className={inputClass}
                required
                pattern="-?[0-9]+"
                maxLength={100}
                title="Informe o ID numérico do Telegram, mantendo o sinal de menos."
                placeholder="Exemplo: -1001234567890"
                value={chatId}
                onChange={(event) => setChatId(event.target.value)}
              />
            </label>
            <label className="block space-y-2 text-sm font-medium">
              <span>
                Nome personalizado{" "}
                <span className="font-normal text-muted-foreground">
                  (opcional)
                </span>
              </span>
              <input
                className={inputClass}
                maxLength={255}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="Usar nome do Telegram"
              />
            </label>
            <p className="text-xs/relaxed text-muted-foreground">
              Deixe em branco para buscar automaticamente o nome do grupo ou
              canal.
            </p>
            <div className="space-y-2">
              <label htmlFor="destination-type" className="text-sm font-medium">
                Tipo de destino
              </label>
              <SelectField
                id="destination-type"
                value={chatType}
                disabled={disabled}
                onValueChange={setChatType}
                options={[
                  { value: "group", label: "Grupo" },
                  { value: "channel", label: "Canal" },
                ]}
              />
            </div>
            <label className="flex min-h-11 items-center gap-3 text-sm">
              <Checkbox
                disabled={disabled}
                checked={enabled}
                onCheckedChange={setEnabled}
              />
              Habilitar publicação neste destino
            </label>
          </fieldset>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={disabled}>
              <Save aria-hidden="true" />
              {settings.busy === "destinations"
                ? "Salvando…"
                : "Salvar destino"}
            </Button>
            {editingId ? (
              <Button
                type="button"
                variant="outline"
                disabled={disabled}
                onClick={reset}
              >
                <X aria-hidden="true" />Cancelar edição
              </Button>
            ) : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
