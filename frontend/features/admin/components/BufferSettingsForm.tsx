"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { checkBufferSettings, saveBufferSettings } from "../api/x-buffer-client";
import type { BufferState } from "../api/x-buffer-types";

const input = "mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm";
const statuses: Record<string, string> = {
  reserved: "Reservado", buffer_sent: "Publicado", buffer_accepted: "Recebido pelo Buffer",
  buffer_blocked: "Conexão indisponível", buffer_rejected: "Recusado", buffer_uncertain: "Envio não confirmado",
  expired: "Expirado", sent: "Publicado", draft_sent: "Rascunho enviado",
};

export function BufferSettingsForm({ initial }: { initial: BufferState }) {
  const [state, setState] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const { settings } = state;

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
        enabled: data.get("enabled") === "on",
        destination_id: Number(data.get("destination_id")) || null,
        channel_id: String(data.get("channel_id") ?? "").trim(),
        landing_url: String(data.get("landing_url") ?? "").trim(),
        daily_limit: Number(data.get("daily_limit")),
        ...(key ? { api_key: key } : {}),
      });
      setState(updated);
      const keyInput = form.elements.namedItem("api_key");
      if (keyInput instanceof HTMLInputElement) keyInput.value = "";
      return "Configuração salva.";
    });
  }

  return (
    <div className="grid max-w-3xl gap-5">
      <form method="post" onSubmit={save} className="grid gap-4 rounded-xl border p-4 sm:p-6">
        {!state.dashboard_managed && <p className="text-sm text-muted-foreground">O ambiente controla o worker. Para ativar o controle pelo painel, use X_OFFERS_MODE=dashboard.</p>}
        <fieldset disabled={busy} className="grid gap-4">
          <label className="flex items-center gap-2 text-sm font-medium"><input type="checkbox" name="enabled" defaultChecked={settings.enabled} /> Ativar publicação automática</label>
          <label className="text-sm font-medium">Destino que já recebe as ofertas
            <select name="destination_id" className={input} defaultValue={settings.destination_id ?? ""}>
              <option value="">Selecione um destino</option>
              {state.destinations.map((dest) => <option key={dest.id} value={dest.id}>{dest.title || dest.chat_id} · {dest.platform} · usuário {dest.user_id}</option>)}
            </select>
          </label>
          <label className="text-sm font-medium">URL pública da VSM
            <input className={input} name="landing_url" type="url" maxLength={1000} defaultValue={settings.landing_url} />
          </label>
          <label className="text-sm font-medium">ID do canal do X no Buffer
            <input className={input} name="channel_id" maxLength={128} defaultValue={settings.channel_id} />
          </label>
          <label className="text-sm font-medium">Chave da API do Buffer
            <input className={input} name="api_key" type="password" autoComplete="new-password" maxLength={4096} placeholder={settings.has_api_key ? "Salva · deixe vazio para manter" : "Informe a chave pessoal"} />
          </label>
          <label className="text-sm font-medium">Limite por dia
            <select className={input} name="daily_limit" defaultValue={settings.daily_limit}>
              <option value="1">1 oferta</option><option value="2">2 ofertas</option>
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <Button type="submit">Salvar</Button>
            <Button type="button" variant="outline" disabled={!settings.has_api_key} onClick={() => void run(async () => `Conexão validada: ${(await checkBufferSettings()).account}.`)}>Testar conexão salva</Button>
          </div>
        </fieldset>
        {notice && <p role="status" className="text-sm">{notice}</p>}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      </form>
      <section className="rounded-xl border p-4 sm:p-6">
        <h2 className="font-semibold">Últimas tentativas</h2>
        {!state.attempts.length && <p className="mt-2 text-sm text-muted-foreground">Nenhuma tentativa registrada.</p>}
        <ul className="mt-2 grid gap-2 text-sm">
          {state.attempts.map((attempt, index) => <li key={`${attempt.attempted_at}-${index}`} className="flex justify-between gap-3"><time dateTime={attempt.attempted_at}>{new Date(attempt.attempted_at).toLocaleString("pt-BR", { timeZone: "America/Sao_Paulo" })}</time><span>{statuses[attempt.status] ?? attempt.status}</span></li>)}
        </ul>
      </section>
    </div>
  );
}
