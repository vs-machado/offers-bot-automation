"use client";

import { useId, useRef, useState, type ReactNode } from "react";
import { Dialog } from "@base-ui/react/dialog";
import { Loader2, ShieldCheck, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCredentialValidation } from "@/features/credential-validation/hooks/use-credential-validation";
import type { ProviderType } from "@/lib/affiliate-providers";

export function CredentialValidation({
  provider,
  credentials,
  disabled = false,
  children,
}: {
  provider: ProviderType;
  credentials: Record<string, string>;
  disabled?: boolean;
  children?: ReactNode;
}) {
  const validation = useCredentialValidation(provider, credentials);
  const [isProductDialogOpen, setIsProductDialogOpen] = useState(false);
  const [portalContainer, setPortalContainer] = useState<HTMLElement>();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const productUrlId = useId();
  const helpId = useId();
  const result = validation.currentValidation?.result;
  const error = validation.currentValidation?.error;
  const isAmazon = provider === "amazon";
  const isMercadoLivre = provider === "mercado_livre";
  const isDisabled = disabled || validation.isValidating;
  const buttonLabel = validation.isValidating
    ? "Validando…"
    : isAmazon
      ? "Validar tag"
      : "Validar credenciais";
  const helpText = isAmazon
    ? "Confere apenas o formato da tag, sem autenticar na Amazon nem confirmar conta, elegibilidade ou comissões. Não salva alterações."
    : "Gera um link de referência na loja, sem publicar ofertas nem salvar alterações. Valide novamente após alterar os dados.";
  const feedback = (
    <div aria-live="polite" className="empty:hidden">
      {result ? (
        <div
          className={`rounded-lg p-3 text-sm ${
            result.status === "valid"
              ? "bg-primary/10 text-primary"
              : result.status === "invalid"
                ? "bg-destructive/10 text-destructive"
                : "bg-muted text-muted-foreground"
          }`}
        >
          <p className="font-semibold">
            {result.status === "valid"
              ? isAmazon
                ? "Formato da tag válido"
                : "Validação aprovada"
              : result.status === "invalid"
                ? isAmazon
                  ? "Tag inválida"
                  : "Credenciais recusadas"
                : "Validação inconclusiva"}
          </p>
          <p className="mt-1">{result.message}</p>
          <p className="mt-2 text-xs">
            Verificado em {new Intl.DateTimeFormat("pt-BR", {
              dateStyle: "short",
              timeStyle: "short",
              timeZone: "America/Sao_Paulo",
            }).format(new Date(result.checked_at))} (Brasília)
          </p>
        </div>
      ) : null}
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {isMercadoLivre ? (
          <Dialog.Root
            open={isProductDialogOpen}
            onOpenChange={(open) => {
              if (open) {
                setPortalContainer(
                  triggerRef.current?.closest<HTMLElement>('[role="dialog"]') ??
                    undefined,
                );
              }
              setIsProductDialogOpen(open);
            }}
          >
            <Dialog.Trigger
              render={
                <Button
                  ref={triggerRef}
                  type="button"
                  variant="outline"
                  disabled={isDisabled}
                  aria-describedby={helpId}
                  title={helpText}
                />
              }
            >
              <ShieldCheck className="size-4" />Validar credenciais
            </Dialog.Trigger>
            <Dialog.Portal container={portalContainer}>
              <Dialog.Backdrop className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm" />
              <Dialog.Popup className="fixed left-1/2 top-1/2 z-50 max-h-[calc(100dvh-2rem)] w-[calc(100%-2rem)] max-w-lg -translate-1/2 space-y-5 overflow-y-auto rounded-2xl border bg-background p-5 text-foreground shadow-lg outline-none sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <Dialog.Title className="pt-2 text-lg font-semibold">
                    Validar Mercado Livre
                  </Dialog.Title>
                  <Dialog.Close
                    render={
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        aria-label="Fechar validação"
                      />
                    }
                  >
                    <X className="size-4" />
                  </Dialog.Close>
                </div>
                <Dialog.Description className="text-sm/6 text-muted-foreground">
                  Informe um produto elegível para testar a geração do seu link de afiliado. O link serve apenas à validação e não será publicado nem salvo.
                </Dialog.Description>
                <form
                  className="space-y-4"
                  onSubmit={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    void validation.validate();
                  }}
                >
                  <div className="space-y-2">
                    <label
                      htmlFor={productUrlId}
                      className="block text-sm font-medium"
                    >
                      Link completo do produto
                    </label>
                    <input
                      id={productUrlId}
                      className="h-11 w-full rounded-lg border border-input bg-background px-3 text-base text-foreground outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50"
                      type="url"
                      required
                      maxLength={2000}
                      placeholder="https://produto.mercadolivre.com.br/MLB-…"
                      value={validation.productUrl}
                      disabled={isDisabled}
                      onChange={(event) =>
                        validation.setProductUrl(event.target.value)
                      }
                    />
                  </div>
                  <Button type="submit" disabled={isDisabled}>
                    {validation.isValidating ? (
                      <Loader2 className="size-4 animate-spin" />
                    ) : (
                      <ShieldCheck className="size-4" />
                    )}
                    {buttonLabel}
                  </Button>
                </form>
                {feedback}
              </Dialog.Popup>
            </Dialog.Portal>
          </Dialog.Root>
        ) : (
          <Button
            type="button"
            variant="outline"
            disabled={isDisabled}
            aria-describedby={helpId}
            title={helpText}
            onClick={() => void validation.validate()}
          >
            {validation.isValidating ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <ShieldCheck className="size-4" />
            )}
            {buttonLabel}
          </Button>
        )}
        {children}
      </div>
      {!isProductDialogOpen ? feedback : null}
      <p id={helpId} className="sr-only">
        {helpText}
      </p>
    </div>
  );
}
