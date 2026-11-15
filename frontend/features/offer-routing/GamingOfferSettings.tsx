"use client";

import { Button } from "@/components/ui/button";
import { SelectField } from "@/components/ui/select";
import { useGamingPolicy } from "./hooks/use-gaming-policy";

const options = [
  { value: "100", label: "Todas (sem redução)" },
  { value: "75", label: "Manter 75% (reduzir 25%)" },
  { value: "50", label: "Manter 50% (reduzir metade)" },
  { value: "25", label: "Manter 25% (reduzir 75%)" },
  { value: "10", label: "Manter 10% (reduzir 90%)" },
  { value: "0", label: "Não enviar ofertas gamer" },
];

export function GamingOfferSettings() {
  const settings = useGamingPolicy();
  const { policy, setPolicy } = settings;
  const disabled = settings.isLoading || settings.isSaving;
  return (
    <section id="gaming-filter" className="space-y-4 rounded-xl border bg-card p-5 sm:p-6" aria-labelledby="gaming-filter-title">
      <div>
        <h3 id="gaming-filter-title" className="font-semibold">Reduzir ofertas gamer</h3>
        <p className="mt-2 text-sm/relaxed text-muted-foreground">
          Escolha quanto das ofertas de jogos, consoles e produtos gamer manter em cada plataforma.
          A seleção é estável por produto: uma oferta descartada não ganha novas chances ao ser repetida.
          Percentuais são aproximados, não um limite diário. Outras ofertas continuam seguindo suas categorias.
        </p>
      </div>
      {settings.error ? <p role="alert" className="text-sm text-destructive">{settings.error} <Button variant="outline" onClick={settings.retry} disabled={disabled}>Recarregar</Button></p> : null}
      {settings.message ? <p role="status" className="text-sm text-primary">{settings.message}</p> : null}
      {settings.isLoading ? <p className="text-sm text-muted-foreground">Carregando filtro gamer…</p> : null}
      <fieldset disabled={disabled || Boolean(settings.error)} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          {(["whatsapp", "telegram"] as const).map((platform) => (
            <div key={platform} className="space-y-2">
              <label htmlFor={`gaming-${platform}`} className="text-sm font-medium">Padrão {platform === "whatsapp" ? "WhatsApp" : "Telegram"}</label>
              <SelectField id={`gaming-${platform}`} value={String(policy.platforms[platform] ?? 100)} options={options} disabled={disabled} onValueChange={(value) => setPolicy({ ...policy, platforms: { ...policy.platforms, [platform]: Number(value) } })} />
            </div>
          ))}
        </div>
        <details className="rounded-lg border p-4">
          <summary className="cursor-pointer text-sm font-medium">Personalizar por grupo ou canal</summary>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {settings.destinations.map((destination) => (
              <div key={destination.id} className="space-y-2">
                <label htmlFor={`gaming-destination-${destination.id}`} className="block text-sm font-medium">
                  {destination.title || destination.chat_id} · {destination.platform === "whatsapp" ? "WhatsApp" : "Telegram"} · {destination.chat_type === "channel" ? "Canal" : "Grupo"}
                </label>
                <SelectField id={`gaming-destination-${destination.id}`} value={String(policy.destinations[destination.chat_id] ?? "inherit")} options={[{ value: "inherit", label: "Usar padrão da plataforma" }, ...options]} disabled={disabled} onValueChange={(value) => {
                  const overrides = { ...policy.destinations };
                  if (value === "inherit") delete overrides[destination.chat_id];
                  else overrides[destination.chat_id] = Number(value);
                  setPolicy({ ...policy, destinations: overrides });
                }} />
              </div>
            ))}
          </div>
        </details>
        <Button onClick={() => void settings.save()} disabled={disabled || Boolean(settings.error)}>{settings.isSaving ? "Salvando…" : "Salvar filtro gamer"}</Button>
      </fieldset>
    </section>
  );
}
