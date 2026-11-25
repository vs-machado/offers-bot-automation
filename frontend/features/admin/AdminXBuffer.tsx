import { Send } from "lucide-react";
import { getAdminBufferState } from "./api/admin-server";
import { BufferSettingsForm } from "./components/BufferSettingsForm";

export async function AdminXBuffer() {
  const initial = await getAdminBufferState();
  return (
    <>
      <header className="flex items-start gap-4">
        <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
          <Send aria-hidden="true" className="size-5" />
        </span>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">Publicação no X</h1>
          <p className="mt-1 text-sm text-muted-foreground">Conecte o Buffer e publique as melhores ofertas da VSM.</p>
        </div>
      </header>
      <BufferSettingsForm initial={initial} />
    </>
  );
}
