import { getSettingsData } from "@/features/settings/api/settings-server";
import { SettingsEditor } from "@/features/settings/components/SettingsEditor";

export async function Settings() {
  const data = await getSettingsData();
  return (
    <>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Configurações
        </h1>
        <p className="mt-2 max-w-prose text-sm/relaxed text-muted-foreground sm:text-base">
          Gerencie seus destinos, grupos de origem e programas de afiliados.
          Alterações entram em vigor em até 30 segundos.
        </p>
      </header>
      <SettingsEditor initialData={data} />
    </>
  );
}
