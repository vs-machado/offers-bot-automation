"use client";

import { Tabs } from "@base-ui/react/tabs";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DestinationSettings } from "@/features/settings/components/DestinationSettings";
import { WhatsAppSettings } from "@/features/settings/components/WhatsAppSettings";
import { ProviderSettings } from "@/features/settings/components/ProviderSettings";
import { useSettings } from "@/features/settings/hooks/use-settings";
import type { SettingsData, SettingsSection } from "@/features/settings/types";
import { affiliateProviders } from "@/lib/affiliate-providers";
import { SourceGroups } from "@/features/source-groups/SourceGroups";
import { DestinationRouting } from "@/features/offer-routing/DestinationRouting";

export function SettingsEditor({
  initialData,
  section,
}: {
  initialData: SettingsData;
  section: SettingsSection;
}) {
  const settings = useSettings(initialData);
  const searchParams = useSearchParams();
  const selectedProvider = affiliateProviders.find(
    (provider) => provider.type === searchParams.get("provider"),
  )?.type ?? affiliateProviders[0].type;
  const configuredSources = settings.configs.find(
    (config) => config.config_type === "source_chats",
  )?.config_data?.source_chats;
  const hasUnavailableSources =
    Array.isArray(configuredSources) &&
    configuredSources.some(
      (url) => !initialData.sources.some((source) => source.url === url),
    );
  return (
    <div className="space-y-6">
      <div aria-live="polite" className="empty:hidden">
        {settings.error ? (
          <p
            role="alert"
            className="rounded-xl border border-destructive/30 bg-background p-4 text-sm text-destructive"
          >
            {settings.error}
          </p>
        ) : null}
        {settings.message ? (
          <p className="rounded-xl border border-primary/30 bg-background p-4 text-sm text-primary">
            {settings.message}
          </p>
        ) : null}
      </div>
      {section === "destinations" ? (
        <div className="space-y-6">
          <DestinationRouting destinations={settings.destinations.filter((destination) => destination.platform !== "whatsapp")} saveDestination={settings.saveDestination} disabled={Boolean(settings.busy)} />
          <DestinationSettings
            settings={{
              ...settings,
              destinations: settings.destinations.filter(
                (destination) => destination.platform !== "whatsapp",
              ),
            }}
          />
          <WhatsAppSettings />
        </div>
      ) : null}
      {section === "sources" ? (
        <Card id="sources" className="gap-0 overflow-hidden py-0">
          <CardHeader className="border-b p-5 sm:p-6">
            <CardTitle>Configurar origens de ofertas</CardTitle>
            <p className="max-w-prose text-sm/6 text-muted-foreground">
              Escolha entre os grupos disponibilizados pela administração. Para
              interromper a captura, desmarque todos e salve.
            </p>
          </CardHeader>
          <CardContent className="space-y-5 p-5 sm:p-6">
            {hasUnavailableSources ? (
              <p className="rounded-lg bg-muted p-3 text-sm">
                Alguns grupos selecionados anteriormente foram desativados pela
                administração. Ao salvar, serão mantidos apenas os grupos
                disponíveis marcados abaixo.
              </p>
            ) : null}
            <SourceGroups
              catalog={initialData.sources}
              selectedSources={settings.selectedSources}
              onSelectionChange={settings.setSelectedSources}
              disabled={Boolean(settings.busy)}
            />
            <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-4">
              <p className="text-xs text-muted-foreground">
                {settings.selectedSources.length} grupos selecionados
              </p>
              <Button
                disabled={Boolean(settings.busy)}
                onClick={() => void settings.saveSources()}
              >
                {settings.busy === "sources"
                  ? "Salvando…"
                  : "Salvar grupos de origem"}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
      {section === "affiliates" ? (
        <section
          id="affiliates"
          className="space-y-4"
          aria-labelledby="affiliates-title"
        >
          <div>
            <h2 id="affiliates-title" className="text-xl font-semibold">
              Programas de afiliados
            </h2>
            <p className="mt-2 max-w-prose text-sm/6 text-muted-foreground">
              Cadastre suas lojas e valide as credenciais. Acompanhe os resultados
              dos envios no histórico de publicações.
            </p>
          </div>
          <Tabs.Root
            key={selectedProvider}
            defaultValue={selectedProvider}
            orientation="vertical"
            className="grid items-start gap-4 md:grid-cols-[13rem_minmax(0,1fr)] md:gap-6"
          >
            <Tabs.List
              aria-label="Lojas de afiliados"
              className="flex flex-col gap-1 rounded-xl border bg-card p-2"
            >
              {affiliateProviders.map((provider) => {
                const isConfigured = settings.configs.some(
                  (config) => config.config_type === provider.type,
                );
                return (
                  <Tabs.Tab
                    key={provider.type}
                    value={provider.type}
                    className="flex min-h-16 items-center gap-3 rounded-lg p-3 text-left outline-none hover:bg-muted focus-visible:ring-2 focus-visible:ring-ring data-active:bg-primary/10 data-active:text-primary"
                  >
                    <span className="flex-1">
                      <span className="block text-sm font-semibold">
                        {provider.name}
                      </span>
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {isConfigured ? "Cadastrada" : "Não cadastrada"}
                      </span>
                    </span>
                  </Tabs.Tab>
                );
              })}
            </Tabs.List>
            <div className="min-w-0">
              {affiliateProviders.map((provider) => (
                <Tabs.Panel
                  key={provider.type}
                  value={provider.type}
                  keepMounted
                  className="outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <ProviderSettings provider={provider} settings={settings} />
                </Tabs.Panel>
              ))}
            </div>
          </Tabs.Root>
        </section>
      ) : null}
    </div>
  );
}
