"use client";

import { useState, type FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SettingsState } from "@/features/settings/hooks/use-settings";
import { getProviderData, type Provider } from "@/lib/affiliate-providers";
import { CredentialValidation } from "@/features/credential-validation/CredentialValidation";

export function ProviderSettings({ provider, settings }: { provider: Provider; settings: SettingsState }) {
  const [fields, setFields] = useState(() => getProviderData(provider, settings.configs));
  const [confirmRemoval, setConfirmRemoval] = useState(false);
  const isConfigured = settings.configs.some((config) => config.config_type === provider.type);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await settings.saveProvider(provider.type, Object.fromEntries(Object.entries(fields).map(([key, value]) => [key, value.trim()])));
  }
  async function remove() {
    if (await settings.disconnectProvider(provider.type)) {
      setFields(Object.fromEntries(provider.fields.map((field) => [field.key, ""])));
      setConfirmRemoval(false);
    }
  }
  return <Card><CardHeader><div className="flex flex-wrap items-center justify-between gap-2"><CardTitle>{provider.name}</CardTitle><span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">{isConfigured ? "Cadastrada" : "Não cadastrada"}</span></div><p className="text-sm/6 text-muted-foreground">{provider.description}</p></CardHeader><CardContent>
    <form onSubmit={submit} className="space-y-4">
      {provider.fields.map((field) => <label key={field.key} className="block space-y-2 text-sm font-medium"><span>{field.label}{field.required ? " *" : ""}</span><input className="h-11 w-full rounded-lg border border-border bg-background px-3 text-foreground" type={/secret|cookie|token|app_key/.test(field.key) ? "password" : "text"} autoComplete="off" required={field.required} disabled={Boolean(settings.busy)} placeholder={field.placeholder} value={fields[field.key] ?? ""} onChange={(event) => setFields((current) => ({ ...current, [field.key]: event.target.value }))} /></label>)}
      <div className="flex flex-wrap gap-2"><Button type="submit" disabled={Boolean(settings.busy)}>{settings.busy === provider.type ? "Salvando…" : "Salvar credenciais"}</Button>{isConfigured ? <Button type="button" variant="outline" disabled={Boolean(settings.busy)} onClick={() => setConfirmRemoval(true)}>Remover integração</Button> : null}</div>
    </form>
    <div className="mt-4"><CredentialValidation provider={provider.type} credentials={fields} disabled={Boolean(settings.busy)} /></div>
    {confirmRemoval ? <div className="mt-4 rounded-lg border border-border bg-muted p-3 text-sm"><p>Remover a integração com {provider.name}? As ofertas dessa loja deixarão de ser publicadas.</p><div className="mt-3 flex gap-2"><Button variant="destructive" disabled={Boolean(settings.busy)} onClick={() => void remove()}>Confirmar remoção</Button><Button variant="outline" disabled={Boolean(settings.busy)} onClick={() => setConfirmRemoval(false)}>Cancelar</Button></div></div> : null}
  </CardContent></Card>;
}
