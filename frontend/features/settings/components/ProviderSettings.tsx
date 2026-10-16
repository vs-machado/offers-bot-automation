"use client";

import { useState, type FormEvent } from "react";
import { Popover } from "@base-ui/react/popover";
import { CircleHelp } from "lucide-react";
import Image from "next/image";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SettingsState } from "@/features/settings/hooks/use-settings";
import { getProviderData, type Provider } from "@/lib/affiliate-providers";
import { CredentialValidation } from "@/features/credential-validation/CredentialValidation";

export function ProviderSettings({
  provider,
  settings,
}: {
  provider: Provider;
  settings: SettingsState;
}) {
  const [fields, setFields] = useState(() =>
    getProviderData(provider, settings.configs),
  );
  const [confirmRemoval, setConfirmRemoval] = useState(false);
  const isConfigured = settings.configs.some(
    (config) => config.config_type === provider.type,
  );
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await settings.saveProvider(
      provider.type,
      Object.fromEntries(
        Object.entries(fields).map(([key, value]) => [key, value.trim()]),
      ),
    );
  }
  async function remove() {
    if (await settings.disconnectProvider(provider.type)) {
      setFields(
        Object.fromEntries(provider.fields.map((field) => [field.key, ""])),
      );
      setConfirmRemoval(false);
    }
  }
  return (
    <Card className="gap-0 overflow-hidden py-0">
      <CardHeader className="border-b p-5 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <CardTitle>{provider.name}</CardTitle>
            {provider.type === "shopee" ? (
              <Popover.Root>
                <Popover.Trigger
                  aria-label="Ajuda sobre credenciais da Shopee"
                  className="inline-flex size-11 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                  <CircleHelp aria-hidden="true" className="size-4" />
                </Popover.Trigger>
                <Popover.Portal>
                  <Popover.Positioner sideOffset={8} className="z-50">
                    <Popover.Popup className="w-80 max-w-[calc(100vw-2rem)] rounded-xl border border-border bg-background p-4 text-sm/6 text-foreground shadow-lg">
                      <Popover.Title className="mb-2 font-semibold">
                        Credenciais da Shopee
                      </Popover.Title>
                      <p>
                        Requer credenciais de API:{" "}
                        <a
                          href="https://affiliate.shopee.com.br/open_api"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary underline underline-offset-4"
                        >
                          Acessar API de afiliados
                        </a>
                      </p>
                      <p className="mt-2">
                        Como solicitar:{" "}
                        <a
                          href="https://seller.br.shopee.cn/edu/article/3445/API--Access-Request-Process"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary underline underline-offset-4"
                        >
                          Processo de solicitação de acesso
                        </a>
                      </p>
                      <Image
                        src="/shopee_api.png"
                        alt="Exemplo da tela Meu API da Shopee com AppID e senha ocultos"
                        width={322}
                        height={172}
                        className="mt-3 h-auto w-full rounded-lg border border-border"
                      />
                    </Popover.Popup>
                  </Popover.Positioner>
                </Popover.Portal>
              </Popover.Root>
            ) : null}
          </div>
          <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
            {isConfigured ? "Cadastrada" : "Não cadastrada"}
          </span>
        </div>
        <p className="text-sm/6 text-muted-foreground">
          {provider.description}
        </p>
      </CardHeader>
      <CardContent className="p-5 sm:p-6">
        <form onSubmit={submit} className="space-y-4">
          {provider.fields.map((field) => (
            <label
              key={field.key}
              className="block space-y-2 text-sm font-medium"
            >
              <span>
                {field.label}
                {field.required ? " *" : ""}
              </span>
              <input
                className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
                type={
                  /secret|cookie|token|app_key/.test(field.key)
                    ? "password"
                    : "text"
                }
                autoComplete="off"
                required={field.required}
                disabled={Boolean(settings.busy)}
                placeholder={field.placeholder}
                value={fields[field.key] ?? ""}
                onChange={(event) =>
                  setFields((current) => ({
                    ...current,
                    [field.key]: event.target.value,
                  }))
                }
              />
            </label>
          ))}
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={Boolean(settings.busy)}>
              {settings.busy === provider.type
                ? "Salvando…"
                : provider.type === "amazon"
                  ? "Salvar tag"
                  : "Salvar credenciais"}
            </Button>
            {isConfigured ? (
              <Button
                type="button"
                variant="outline"
                disabled={Boolean(settings.busy)}
                onClick={() => setConfirmRemoval(true)}
              >
                Remover integração
              </Button>
            ) : null}
          </div>
        </form>
        <div className="mt-4">
          <CredentialValidation
            provider={provider.type}
            credentials={fields}
            disabled={Boolean(settings.busy)}
          />
        </div>
        {confirmRemoval ? (
          <div className="mt-4 rounded-lg border border-border bg-muted p-3 text-sm">
            <p>
              Remover a integração com {provider.name}? As ofertas dessa loja
              deixarão de ser publicadas.
            </p>
            <div className="mt-3 flex gap-2">
              <Button
                variant="destructive"
                disabled={Boolean(settings.busy)}
                onClick={() => void remove()}
              >
                Confirmar remoção
              </Button>
              <Button
                variant="outline"
                disabled={Boolean(settings.busy)}
                onClick={() => setConfirmRemoval(false)}
              >
                Cancelar
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
