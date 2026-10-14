import Link from "next/link";
import { ArrowLeft, Settings as SettingsIcon } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { getSettingsData } from "@/features/settings/api/settings-server";
import { SettingsEditor } from "@/features/settings/components/SettingsEditor";

export async function Settings() {
  const data = await getSettingsData();
  return (
    <main className="min-h-dvh bg-background text-foreground">
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
        <div className="mb-8 flex items-center justify-between gap-4"><Link href="/dashboard" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" />Voltar ao painel</Link><ThemeToggle /></div>
        <header className="mb-8"><p className="mb-3 flex items-center gap-2 text-sm font-medium text-primary"><SettingsIcon className="size-4" />Configurações do bot</p><h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Sua automação, do seu jeito</h1><p className="mt-3 max-w-2xl text-sm/6 text-muted-foreground">Atualize seus grupos e credenciais de afiliado sempre que precisar. As alterações serão usadas pelo bot após a próxima atualização da configuração, em até 30 segundos.</p></header>
        <SettingsEditor initialData={data} />
      </div>
    </main>
  );
}
