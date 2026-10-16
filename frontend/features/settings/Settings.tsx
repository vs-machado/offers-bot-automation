import { getSettingsData } from "@/features/settings/api/settings-server";
import { SettingsEditor } from "@/features/settings/components/SettingsEditor";
import type { SettingsSection } from "@/features/settings/types";

const sections = {
  destinations: {
    title: "Destinos",
    description:
      "Configure Telegram e WhatsApp e escolha onde publicar suas ofertas.",
  },
  sources: {
    title: "Origens de ofertas",
    description: "Escolha os grupos do Telegram de onde o bot vai copiar ofertas.",
  },
  affiliates: {
    title: "Afiliados",
    description:
      "Cadastre suas lojas e valide as credenciais usadas para gerar seus links de afiliado.",
  },
};

export async function Settings({ section }: { section: SettingsSection }) {
  const data = await getSettingsData(section);
  const { title, description } = sections[section];
  return (
    <>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          {title}
        </h1>
        <p className="mt-2 max-w-prose text-sm/relaxed text-muted-foreground sm:text-base">
          {description} Alterações entram em vigor em até 30 segundos.
        </p>
      </header>
      <SettingsEditor key={section} initialData={data} section={section} />
    </>
  );
}
