"use client";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { DestinationSettings } from "@/features/settings/components/DestinationSettings";
import { WhatsAppSettings } from "@/features/settings/components/WhatsAppSettings";
import { ProviderSettings } from "@/features/settings/components/ProviderSettings";
import { useSettings } from "@/features/settings/hooks/use-settings";
import type { SettingsData } from "@/features/settings/types";
import { affiliateProviders } from "@/lib/affiliate-providers";

export function SettingsEditor({ initialData }: { initialData: SettingsData }) {
  const settings = useSettings(initialData);
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
      <nav
        aria-label="Seções das configurações"
        className="sticky top-0 z-10 flex flex-wrap gap-1 rounded-xl border bg-background p-1 text-sm font-medium shadow-xs [&_a]:inline-flex [&_a]:min-h-11 [&_a]:items-center [&_a]:rounded-lg [&_a]:px-3 [&_a]:text-muted-foreground [&_a]:outline-none [&_a:hover]:bg-accent [&_a:hover]:text-accent-foreground [&_a:focus-visible]:ring-2 [&_a:focus-visible]:ring-ring"
      >
        <a href="#destinations">Telegram</a>
        <a href="#whatsapp">WhatsApp</a>
        <a href="#sources">Grupos de origem</a>
        <a href="#affiliates">Afiliados</a>
      </nav>
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
      <DestinationSettings
        settings={{
          ...settings,
          destinations: settings.destinations.filter(
            (destination) => destination.platform !== "whatsapp",
          ),
        }}
      />
      <WhatsAppSettings settings={settings} />
      <Card id="sources" className="scroll-mt-32 gap-0 overflow-hidden py-0">
        <CardHeader className="border-b p-5 sm:p-6">
          <CardTitle>De onde copiar ofertas</CardTitle>
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
          <fieldset
            disabled={Boolean(settings.busy)}
            className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"
          >
            <legend className="sr-only">Grupos de origem disponíveis</legend>
            {initialData.sources.map((source) => (
              <label
                key={source.url}
                className="flex min-h-14 cursor-pointer items-center gap-3 rounded-xl border border-border p-4 text-sm hover:bg-muted/50 has-checked:border-primary has-checked:bg-primary/5"
              >
                <input
                  type="checkbox"
                  className="size-4 shrink-0 accent-primary"
                  checked={settings.selectedSources.includes(source.url)}
                  onChange={(event) =>
                    settings.setSelectedSources((current) =>
                      event.target.checked
                        ? [...current, source.url]
                        : current.filter((url) => url !== source.url),
                    )
                  }
                />
                <span className="min-w-0 wrap-anywhere">{source.label}</span>
              </label>
            ))}
          </fieldset>
          {!initialData.sources.length ? (
            <p className="text-sm text-muted-foreground">
              Nenhum grupo de origem está disponível no momento.
            </p>
          ) : null}
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
      <section
        id="affiliates"
        className="scroll-mt-32 space-y-4"
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
        <div className="grid items-start gap-6 xl:grid-cols-2">
          {affiliateProviders.map((provider) => (
            <ProviderSettings
              key={provider.type}
              provider={provider}
              settings={settings}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
