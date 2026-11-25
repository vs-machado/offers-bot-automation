import Link from "next/link";
import { getAdminBufferState } from "./api/admin-server";
import { BufferSettingsForm } from "./components/BufferSettingsForm";

export async function AdminXBuffer() {
  const initial = await getAdminBufferState();
  return (
    <>
      <header>
        <Link href="/admin/source-groups" className="text-sm text-primary underline">Administração</Link>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">Publicação no X</h1>
        <p className="mt-2 text-sm text-muted-foreground">Envie as melhores ofertas para o X com o Share Now do Buffer.</p>
      </header>
      <BufferSettingsForm initial={initial} />
    </>
  );
}
