import Link from "next/link";
import { ArrowLeft, ShieldCheck } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { getAdminSourceGroups } from "@/features/admin/api/admin-server";
import { SourceCatalogEditor } from "@/features/admin/components/SourceCatalogEditor";

export async function AdminSourceGroups() {
  const groups = await getAdminSourceGroups();
  return (
    <main className="min-h-[100dvh] bg-background text-foreground">
      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
        <div className="mb-8 flex items-center justify-between gap-4">
          <Link href="/dashboard" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="size-4" />Back to dashboard</Link>
          <ThemeToggle />
        </div>
        <header className="mb-8">
          <p className="mb-3 flex items-center gap-2 text-sm font-medium text-primary"><ShieldCheck className="size-4" />Administration</p>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Telegram source catalog</h1>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-muted-foreground">Choose which groups users can copy offers from. Manage names, availability, and public Telegram links.</p>
        </header>
        <SourceCatalogEditor initialGroups={groups} />
      </div>
    </main>
  );
}
