"use client";

import { TriangleAlert } from "lucide-react";
import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { useIntegrationHealth } from "@/features/dashboard/hooks/use-integration-health";

export function IntegrationAlerts() {
  const { health, hasError } = useIntegrationHealth();
  const alerts = [];
  if (health?.whatsapp === "disconnected") {
    alerts.push({
      title: "WhatsApp desconectado",
      description: "Uma ou mais contas WhatsApp estão desconectadas. Destinos dessas contas não recebem ofertas. Confira conexões e destinos habilitados nas configurações.",
      href: "/settings/destinations#whatsapp",
      action: "Reconectar WhatsApp",
    });
  } else if (health?.whatsapp === "unknown") {
    alerts.push({
      title: "Não foi possível verificar o WhatsApp",
      description: "A conexão está indisponível ou não pôde ser confirmada. Confira o estado da conta em Destinos.",
      href: "/settings/destinations#whatsapp",
      action: "Verificar WhatsApp",
    });
  }
  if (health?.mercado_livre === "expired" || health?.mercado_livre === "incomplete") {
    alerts.push({
      title: health.mercado_livre === "expired" ? "Sessão do Mercado Livre expirada ou inválida" : "Credenciais do Mercado Livre incompletas",
      description: "Atualize os cookies e o token CSRF para voltar a gerar links de afiliado do Mercado Livre.",
      href: "/settings/affiliates?provider=mercado_livre#affiliates",
      action: "Reconfigurar cookies",
    });
  } else if (health?.mercado_livre === "unknown") {
    alerts.push({
      title: "Não foi possível verificar a sessão do Mercado Livre",
      description: "A loja não confirmou o acesso. Isso pode ser temporário e não confirma expiração dos cookies. Confira as credenciais e valide a integração.",
      href: "/settings/affiliates?provider=mercado_livre#affiliates",
      action: "Verificar credenciais",
    });
  }

  return (
    <div aria-live="polite" className="mb-6 shrink-0 space-y-3 empty:hidden">
      {alerts.map((alert) => (
        <section key={alert.href} role="alert" className="flex flex-col gap-4 rounded-xl border border-destructive/40 bg-destructive/5 p-4 sm:flex-row sm:items-center">
          <TriangleAlert aria-hidden="true" className="size-5 shrink-0 text-destructive" />
          <div className="min-w-0 flex-1">
            <h2 className="font-semibold">{alert.title}</h2>
            <p className="mt-1 text-sm/relaxed text-muted-foreground">{alert.description}</p>
          </div>
          <Link href={alert.href} className={buttonVariants({ variant: "outline", className: "min-h-11" })}>
            {alert.action}
          </Link>
        </section>
      ))}
      {hasError ? <p role="status" className="text-sm text-muted-foreground">Não foi possível atualizar os avisos das integrações. Nova tentativa automática em até um minuto.</p> : null}
    </div>
  );
}
