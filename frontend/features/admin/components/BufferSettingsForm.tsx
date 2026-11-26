"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { SelectField } from "@/components/ui/select";
import { checkBufferSettings, saveBufferSettings } from "../api/x-buffer-client";
import type { BufferState } from "../api/x-buffer-types";
import { RecentXPostsPanel } from "./RecentXPostsPanel";

const input = "h-11 w-full rounded-lg border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 sm:text-sm";
const statuses: Record<string, string> = {
  reserved: "Reservado", buffer_sent: "Publicado", buffer_accepted: "Recebido pelo Buffer",
  buffer_blocked: "Conexão indisponível", buffer_rejected: "Recusado", buffer_uncertain: "Envio não confirmado",
  expired: "Expirado", sent: "Publicado", draft_sent: "Rascunho enviado",
};

export function BufferSettingsForm({ initial }: { initial: BufferState }) {
  const [state, setState] = useState(initial);
  const [settingsVersion, setSettingsVersion] = useState(0);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const { settings } = state;
  const [enabled, setEnabled] = useState(settings.enabled);
  const [destination, setDestination] = useState(String(settings.destination_id ?? ""));
  const [dailyLimit, setDailyLimit] = useState(String(settings.daily_limit));
  const [prioritySource, setPrioritySource] = useState(String(settings.priority_source_id ?? ""));
  const priorityOptions = [
    { value: "", label: "Sem preferência" },
    ...state.source_groups.map((source) => ({ value: String(source.id), label: source.label })),
  ];
  if (prioritySource && !priorityOptions.some((option) => option.value === prioritySource)) {
    priorityOptions.push({ value: prioritySource, label: "Grupo não disponível" });
  }
  const destinationOptions = [
    { value: "", label: "Selecione um destino" },
    ...state.destinations.map((dest) => ({
      value: String(dest.id),
      label: `${dest.title || dest.chat_id} · ${dest.platform} · usuário ${dest.user_id}`,
    })),
  ];
  if (destination && !destinationOptions.some((option) => option.value === destination)) {
    destinationOptions.push({ value: destination, label: "Destino não disponível" });
  }

  async function run(action: () => Promise<string>) {
    setBusy(true);
    setNotice("");
    setError("");
    try {
      setNotice(await action());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível concluir a operação.");
    } finally {
      setBusy(false);
    }
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const key = String(data.get("api_key") ?? "").trim();
    void run(async () => {
      const updated = await saveBufferSettings({
        enabled,
        destination_id: Number(destination) || null,
        channel_id: String(data.get("channel_id") ?? "").trim(),
        landing_url: String(data.get("landing_url") ?? "").trim(),
        daily_limit: Number(dailyLimit),
        priority_source_id: Number(prioritySource) || null,
        ...(key ? { api_key: key } : {}),
      });
      setState(updated);
      setSettingsVersion((version) => version + 1);
      const keyInput = form.elements.namedItem("api_key");
      if (keyInput instanceof HTMLInputElement) keyInput.value = "";
      return "Configuração salva.";
    });
  }

  return (
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
      <form method="post" onSubmit={save} className="grid min-w-0 gap-5">
        {!state.dashboard_managed && (
          <p className="rounded-lg border bg-muted/50 p-3 text-sm text-muted-foreground">
            O ambiente controla o worker. Use <code>X_OFFERS_MODE=dashboard</code> para gerenciar pelo painel.
          </p>
        )}
        <Card>
          <CardHeader>
            <CardTitle>Publicação automática</CardTitle>
            <CardDescription>Escolha de onde vêm as ofertas e quantas podem ser publicadas.</CardDescription>
          </CardHeader>
          <CardContent>
            <fieldset disabled={busy} className="grid min-w-0 gap-4">
              <div className="flex items-start gap-3 rounded-xl border bg-muted/30 p-4">
                <Checkbox id="x-buffer-enabled" className="mt-0.5" checked={enabled} onCheckedChange={setEnabled} disabled={busy} aria-describedby="x-buffer-enabled-note" />
                <div>
                  <label htmlFor="x-buffer-enabled" className="font-medium">Ativar publicação automática</label>
                  <p id="x-buffer-enabled-note" className="mt-1 text-sm text-muted-foreground">O Buffer publica ofertas elegíveis assim que o bot as envia.</p>
                </div>
              </div>
              <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_9rem]">
                <div className="grid min-w-0 gap-1.5">
                  <label htmlFor="x-buffer-destination" className="font-medium">Destino que recebe as ofertas</label>
                  <SelectField id="x-buffer-destination" value={destination} options={destinationOptions} onValueChange={setDestination} disabled={busy} />
                </div>
                <div className="grid gap-1.5">
                  <label htmlFor="x-buffer-limit" className="font-medium">Limite diário</label>
                  <SelectField id="x-buffer-limit" value={dailyLimit} options={Array.from({ length: 10 }, (_, i) => ({ value: String(i + 1), label: i === 0 ? "1 oferta" : `${i + 1} ofertas` }))} onValueChange={setDailyLimit} disabled={busy} />
                </div>
              </div>
              <div className="grid gap-1.5">
                <label htmlFor="x-buffer-priority-source" className="font-medium">Grupo de origem prioritário</label>
                <SelectField id="x-buffer-priority-source" value={prioritySource} options={priorityOptions} onValueChange={setPrioritySource} disabled={busy} />
                <p className="text-muted-foreground">Se houver uma oferta elegível deste grupo no destino escolhido, ela terá prioridade.</p>
              </div>
              <label className="grid gap-1.5 font-medium">Página de ofertas da VSM (opcional)
                <input className={input} name="landing_url" type="url" maxLength={1000} defaultValue={settings.landing_url} placeholder="https://…" />
                <span className="font-normal text-muted-foreground">Use este link na bio ou no post fixado. Cada oferta mantém a foto e o link do produto.</span>
              </label>
            </fieldset>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Conexão com o Buffer</CardTitle>
            <CardDescription>Salve os dados e confirme o perfil do X com um teste que não publica.</CardDescription>
          </CardHeader>
          <CardContent>
            <fieldset disabled={busy} className="grid min-w-0 gap-4">
              <label className="grid gap-1.5 font-medium">ID do canal do X no Buffer
                <input className={input} name="channel_id" maxLength={128} defaultValue={settings.channel_id} />
              </label>
              <label className="grid gap-1.5 font-medium">Chave da API do Buffer
                <input className={input} name="api_key" type="password" autoComplete="new-password" maxLength={4096} placeholder={settings.has_api_key ? "Salva · deixe vazio para manter" : "Informe a chave pessoal"} />
              </label>
              <div className="flex flex-wrap gap-2 border-t pt-4">
                <Button type="submit">Salvar configurações</Button>
                <Button type="button" variant="outline" disabled={!settings.has_api_key} onClick={() => void run(async () => `Conexão validada: ${(await checkBufferSettings()).account}.`)}>Testar conexão salva</Button>
              </div>
            </fieldset>
            {notice && <p role="status" className="mt-3 text-sm">{notice}</p>}
            {error && <p role="alert" className="mt-3 text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
      </form>
      <aside aria-label="Atividade no X" className="grid min-w-0 gap-5">
      <RecentXPostsPanel settingsVersion={settingsVersion} />
      <Card>
        <CardHeader>
          <CardTitle>Últimas tentativas</CardTitle>
          <CardDescription>Acompanhe se o Buffer recebeu ou publicou cada oferta.</CardDescription>
        </CardHeader>
        <CardContent>
          {!state.attempts.length ? (
            <p className="rounded-xl border border-dashed p-4 text-sm text-muted-foreground">Nenhuma tentativa registrada.</p>
          ) : (
            <ul className="divide-y">
              {state.attempts.map((attempt, index) => (
                <li key={`${attempt.attempted_at}-${index}`} className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0">
                  <time className="text-xs text-muted-foreground" dateTime={attempt.attempted_at}>{new Date(attempt.attempted_at).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })}</time>
                  <span className="rounded-full bg-muted px-2.5 py-1 text-xs font-medium">{statuses[attempt.status] ?? attempt.status}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
      </aside>
    </div>
  );
}
