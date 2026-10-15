"use client";

import { Loader2, ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCredentialValidation } from "@/features/credential-validation/hooks/use-credential-validation";
import type { ProviderType } from "@/lib/affiliate-providers";

export function CredentialValidation({ provider, credentials, disabled = false }: { provider: ProviderType; credentials: Record<string, string>; disabled?: boolean }) {
  const validation = useCredentialValidation(provider, credentials);
  const result = validation.currentValidation?.result;
  const error = validation.currentValidation?.error;
  const isAmazon = provider === "amazon";
  return <div className="space-y-3 rounded-xl border border-border bg-background p-4">
    {provider === "mercado_livre" ? <label className="block space-y-2 text-sm font-medium"><span>Link de um produto para validar o Mercado Livre</span><input className="h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground" type="url" placeholder="https://produto.mercadolivre.com.br/MLB-…" value={validation.productUrl} disabled={disabled || validation.isValidating} onChange={(event) => validation.setProductUrl(event.target.value)} /><span className="block text-xs/5 text-muted-foreground">Use o endereço completo de um produto elegível para afiliados. O link serve apenas à validação e não será publicado nem salvo.</span></label> : null}
    <Button type="button" variant="outline" disabled={disabled || validation.isValidating} onClick={() => void validation.validate()}>{validation.isValidating ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}{validation.isValidating ? "Validando…" : isAmazon ? "Validar tag" : "Validar credenciais"}</Button>
    <div aria-live="polite">{result ? <div className={`rounded-lg p-3 text-sm ${result.status === "valid" ? "bg-primary/10 text-primary" : result.status === "invalid" ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground"}`}><p className="font-semibold">{result.status === "valid" ? isAmazon ? "Formato da tag válido" : "Validação aprovada" : result.status === "invalid" ? isAmazon ? "Tag inválida" : "Credenciais recusadas" : "Validação inconclusiva"}</p><p className="mt-1">{result.message}</p><p className="mt-2 text-xs">Verificado em {new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" }).format(new Date(result.checked_at))} (Brasília)</p></div> : null}{error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}</div>
    <p className="text-xs/5 text-muted-foreground">{isAmazon ? "A verificação confere apenas o formato da tag, sem autenticar na Amazon nem confirmar sua conta, elegibilidade ou comissões. Os links são expandidos, com sua tag, sem cookies ou SiteStripe. A tag preenchida não é salva pela validação; alterá-la exige nova verificação." : "A verificação gera um link de referência na loja, sem postar no Telegram. Ela usa os dados preenchidos acima e não os salva. Alterar um campo exige nova validação; cookies e permissões podem expirar depois."}</p>
  </div>;
}
