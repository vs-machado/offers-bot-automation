"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DestinationSettings } from "@/features/settings/components/DestinationSettings";
import { ProviderSettings } from "@/features/settings/components/ProviderSettings";
import { useSettings } from "@/features/settings/hooks/use-settings";
import type { SettingsData } from "@/features/settings/types";
import { affiliateProviders } from "@/lib/affiliate-providers";

export function SettingsEditor({ initialData }: { initialData: SettingsData }) {
  const settings = useSettings(initialData);
  const configuredSources = settings.configs.find((config) => config.config_type === "source_chats")?.config_data?.source_chats;
  const hasUnavailableSources = Array.isArray(configuredSources) && configuredSources.some((url) => !initialData.sources.some((source) => source.url === url));
  return <div className="space-y-6">
    <nav aria-label="Seções das configurações" className="flex flex-wrap gap-3 text-sm font-medium text-primary"><a href="#destinations">Destinos</a><a href="#sources">Grupos de origem</a><a href="#affiliates">Afiliados</a></nav>
    <div aria-live="polite" className="sticky top-3 z-10">{settings.error ? <p role="alert" className="rounded-xl border border-destructive/30 bg-background p-4 text-sm text-destructive">{settings.error}</p> : null}{settings.message ? <p className="rounded-xl border border-primary/30 bg-background p-4 text-sm text-primary">{settings.message}</p> : null}</div>
    <DestinationSettings settings={settings} />
    <Card id="sources" className="scroll-mt-6"><CardHeader><CardTitle>De onde copiar ofertas</CardTitle><p className="text-sm/6 text-muted-foreground">Escolha entre os grupos disponibilizados pela administração. Para interromper a captura, desmarque todos e salve.</p></CardHeader><CardContent className="space-y-4">{hasUnavailableSources ? <p className="rounded-lg bg-muted p-3 text-sm">Alguns grupos selecionados anteriormente foram desativados pela administração. Ao salvar, serão mantidos apenas os grupos disponíveis marcados abaixo.</p> : null}<fieldset disabled={Boolean(settings.busy)} className="grid gap-3 sm:grid-cols-2">{initialData.sources.map((source) => <label key={source.url} className="flex items-center gap-3 rounded-lg border border-border p-3 text-sm"><input type="checkbox" checked={settings.selectedSources.includes(source.url)} onChange={(event) => settings.setSelectedSources((current) => event.target.checked ? [...current, source.url] : current.filter((url) => url !== source.url))} /><span>{source.label}</span></label>)}</fieldset>{!initialData.sources.length ? <p className="text-sm text-muted-foreground">Nenhum grupo de origem está disponível no momento.</p> : null}<Button disabled={Boolean(settings.busy)} onClick={() => void settings.saveSources()}>{settings.busy === "sources" ? "Salvando…" : "Salvar grupos de origem"}</Button></CardContent></Card>
    <section id="affiliates" className="scroll-mt-6 space-y-4" aria-labelledby="affiliates-title"><div><h2 id="affiliates-title" className="text-xl font-semibold">Programas de afiliados</h2><p className="mt-2 text-sm/6 text-muted-foreground">Você pode cadastrar as quatro lojas. Salvar as credenciais não confirma que a API as aceitou; acompanhe os resultados no histórico de publicações.</p></div><div className="grid items-start gap-4 lg:grid-cols-2">{affiliateProviders.map((provider) => <ProviderSettings key={provider.type} provider={provider} settings={settings} />)}</div></section>
  </div>;
}
