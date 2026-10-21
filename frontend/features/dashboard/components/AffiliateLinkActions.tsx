"use client";

import { Check, Copy, ExternalLink } from "lucide-react";
import { useState } from "react";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function AffiliateLinkActions({ url }: { url: string | null }) {
  const [status, setStatus] = useState<"idle" | "copied" | "error">("idle");

  async function copyLink() {
    if (!url) return;

    try {
      await navigator.clipboard.writeText(url);
      setStatus("copied");
    } catch {
      setStatus("error");
    }
  }

  if (!url) {
    return (
      <p className="mt-3 text-xs text-muted-foreground">
        Link comissionado indisponível.
      </p>
    );
  }

  return (
    <div className="mt-3 flex flex-wrap items-center gap-2">
      <Button type="button" variant="outline" className="min-h-11" onClick={copyLink}>
        {status === "copied" ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
        Copiar link comissionado
      </Button>
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className={cn(buttonVariants({ variant: "outline" }), "min-h-11")}
        aria-label="Abrir oferta em nova aba"
      >
        <ExternalLink aria-hidden="true" />
        Abrir oferta
      </a>
      <span role="status" className="text-xs text-muted-foreground">
        {status === "copied" ? "Link copiado!" : null}
      </span>
      {status === "error" ? (
        <div role="alert" className="w-full text-xs text-destructive">
          <p>Não foi possível copiar. Selecione e copie o link abaixo:</p>
          <input
            aria-label="Link comissionado"
            readOnly
            value={url}
            onFocus={(event) => event.currentTarget.select()}
            className="mt-2 min-h-11 w-full min-w-0 rounded-md border bg-background px-3 text-foreground"
          />
        </div>
      ) : null}
    </div>
  );
}
