import { getAdminSourceGroups } from "@/features/admin/api/admin-server";
import { SourceCatalogEditor } from "@/features/admin/components/SourceCatalogEditor";

export async function AdminSourceGroups() {
  const groups = await getAdminSourceGroups();
  return (
    <>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Grupos de origem
        </h1>
        <p className="mt-2 max-w-prose text-sm/relaxed text-muted-foreground sm:text-base">
          Gerencie o catálogo do Telegram. Grupos ativos ficam disponíveis para
          os usuários copiarem ofertas.
        </p>
      </header>
      <SourceCatalogEditor initialGroups={groups} />
    </>
  );
}
