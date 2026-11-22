import { getPostingModelSettings } from "@/features/settings/api/settings-server";
import { PostingModelForm } from "@/features/settings/components/PostingModelForm";

export async function PostingModelsSettings() {
  const { catalog, config } = await getPostingModelSettings();

  return (
    <>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
          Modelos de IA
        </h1>
        <p className="mt-2 max-w-prose text-sm/relaxed text-muted-foreground sm:text-base">
          Escolha os modelos que o Offers Bot usa para processar ofertas antes de publicar.
        </p>
      </header>
      <PostingModelForm catalog={catalog} config={config} />
    </>
  );
}
