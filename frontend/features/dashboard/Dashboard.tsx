import { Check, Link2, Radio, Settings2, UsersRound } from "lucide-react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { getSession } from "@/lib/auth-session";
import {
  getDeliveryHistory,
  getDestinations,
  getUserConfigs,
} from "@/features/dashboard/api/dashboard-server";
import { PublicationHistory } from "@/features/dashboard/components/PublicationHistory";
import { IntegrationAlerts } from "@/features/dashboard/components/IntegrationAlerts";
import { SetupDialog } from "@/features/setup/SetupDialog";

export async function Dashboard() {
  const session = await getSession();
  if (!session) redirect("/");

  const [destinations, configs] = await Promise.all([
    getDestinations(session.sessionToken),
    getUserConfigs(session.sessionToken),
  ]);
  const enabledDestinations = destinations.filter(
    (destination) => destination.enabled,
  );
  const hasEnabledDestination = enabledDestinations.length > 0;
  const hasAffiliateConfig = configs.some((config) =>
    ["amazon", "shopee", "mercado_livre", "aliexpress", "awin", "magalu"].includes(
      config.config_type,
    ),
  );
  const sourceConfig = configs.find(
    (config) => config.config_type === "source_chats",
  );
  const sourceChats = sourceConfig?.config_data?.source_chats;
  const sourceCount = Array.isArray(sourceChats) ? sourceChats.length : 0;
  const setupSteps = [
    {
      title: "Escolha onde publicar",
      description:
        "Conecte Telegram ou WhatsApp e habilite um grupo ou canal de destino.",
      complete: hasEnabledDestination,
      icon: UsersRound,
    },
    {
      title: "Configure seus afiliados",
      description:
        "Cadastre suas credenciais para publicar com seus próprios links.",
      complete: hasAffiliateConfig,
      icon: Link2,
    },
    {
      title: "Selecione as origens",
      description:
        "Escolha os grupos do catálogo de onde as ofertas serão copiadas.",
      complete: sourceCount > 0,
      icon: Radio,
    },
  ];
  const completedCount = setupSteps.filter((step) => step.complete).length;
  const isConfigured = completedCount === setupSteps.length;
  const deliveryHistory = isConfigured
    ? await getDeliveryHistory(session.sessionToken)
    : null;

  return (
    <>
      <div className="mb-6 flex shrink-0 flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
            {isConfigured ? "Visão geral" : "Configure sua automação"}
          </h1>
          <p className="mt-2 max-w-prose text-sm/relaxed text-muted-foreground sm:text-base">
            {isConfigured
              ? "Suas ofertas, destinos e publicações em um só lugar."
              : "Três passos para começar a publicar ofertas com seus links de afiliado."}
          </p>
        </div>
        {isConfigured ? (
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-muted-foreground">
            <Link
              href="/settings/destinations"
              className="inline-flex min-h-11 items-center gap-2 underline-offset-4 hover:text-foreground hover:underline focus-visible:outline-2 focus-visible:outline-ring"
            >
              <UsersRound aria-hidden="true" className="size-4" />
              {enabledDestinations.length}{" "}
              {enabledDestinations.length === 1
                ? "destino ativo"
                : "destinos ativos"}
            </Link>
            <span className="inline-flex items-center gap-2">
              <Radio aria-hidden="true" className="size-4" />
              {sourceCount} {sourceCount === 1 ? "origem" : "origens"}
            </span>
          </div>
        ) : null}
      </div>
      <IntegrationAlerts />
      {isConfigured ? (
        <PublicationHistory initialData={deliveryHistory} />
      ) : (
        <Card className="max-w-3xl gap-0 overflow-y-auto py-0 shadow-none ring-1 ring-border">
          <CardContent className="p-5 sm:p-6">
            <div className="flex items-center gap-3">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-muted">
                <Settings2 aria-hidden="true" className="size-5" />
              </span>
              <div>
                <h2 className="text-lg font-semibold">
                  Vamos configurar seu bot
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  {completedCount} de {setupSteps.length} etapas concluídas
                </p>
              </div>
            </div>
            <div
              className="mt-5 flex gap-2"
              aria-label={`${completedCount} de ${setupSteps.length} etapas concluídas`}
            >
              {setupSteps.map((step) => (
                <span
                  key={step.title}
                  className={`h-1.5 flex-1 rounded-full ${step.complete ? "bg-primary" : "bg-muted"}`}
                />
              ))}
            </div>
            <ol className="my-6 divide-y">
              {setupSteps.map(({ icon: Icon, ...step }, index) => (
                <li key={step.title} className="flex items-start gap-4 py-5">
                  <span className="flex size-9 shrink-0 items-center justify-center rounded-full border bg-background text-sm font-medium">
                    {step.complete ? (
                      <Check aria-hidden="true" className="size-4" />
                    ) : (
                      index + 1
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <h3 className="flex items-center gap-2 font-medium">
                      {step.title}
                      <Icon
                        aria-hidden="true"
                        className="size-4 text-muted-foreground"
                      />
                    </h3>
                    <p className="mt-1 text-sm/relaxed text-muted-foreground">
                      {step.description}
                    </p>
                    <p className="mt-2 text-xs font-medium text-muted-foreground">
                      {step.complete ? "Concluído" : "Pendente"}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
            <SetupDialog
              configs={configs}
              destinations={destinations}
              hasEnabledDestination={hasEnabledDestination}
            />
          </CardContent>
        </Card>
      )}
    </>
  );
}
