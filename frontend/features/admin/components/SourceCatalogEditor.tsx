"use client";

import { Loader2, Pencil, Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useSourceCatalog } from "@/features/admin/hooks/use-source-catalog";
import type { AdminSourceGroup } from "@/features/admin/types";

export function SourceCatalogEditor({
  initialGroups,
}: {
  initialGroups: AdminSourceGroup[];
}) {
  const catalog = useSourceCatalog(initialGroups);
  const activeCount = catalog.groups.filter((group) => group.enabled).length;
  const inputClass =
    "h-11 w-full rounded-lg border border-input bg-background px-3 text-base outline-none focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50";

  return (
    <div className="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
      <section
        aria-label="Catálogo de grupos do Telegram"
        className="min-w-0 overflow-hidden rounded-xl border border-border bg-card"
      >
        <div className="flex items-center justify-between gap-3 border-b border-border px-5 py-4">
          <h2 className="font-semibold">Grupos de origem</h2>
          <span className="text-sm text-muted-foreground">
            {activeCount} {activeCount === 1 ? "ativo" : "ativos"} de{" "}
            {catalog.groups.length} no catálogo
          </span>
        </div>
        {catalog.groups.length === 0 ? (
          <p className="p-6 text-sm text-muted-foreground">
            Nenhum grupo cadastrado. Adicione um grupo público do Telegram para
            disponibilizá-lo aos usuários.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {catalog.groups.map((group) => (
              <li key={group.id} className="space-y-3 p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="wrap-break-word font-medium">
                        {group.label}
                      </h3>
                      <span
                        className={
                          group.enabled
                            ? "rounded-full bg-emerald-500/10 px-2 py-0.5 text-xs text-emerald-700 dark:text-emerald-300"
                            : "rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
                        }
                      >
                        {group.enabled ? "Ativo" : "Desativado"}
                      </span>
                    </div>
                    <a
                      href={group.url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 block break-all text-sm text-muted-foreground hover:text-primary"
                    >
                      {group.url}
                    </a>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={catalog.busy}
                      onClick={() => void catalog.toggleGroup(group)}
                    >
                      {group.enabled ? "Desativar" : "Ativar"}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={catalog.busy}
                      aria-label={`Editar ${group.label}`}
                      onClick={() => catalog.editGroup(group)}
                    >
                      <Pencil className="size-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={catalog.busy}
                      aria-label={`Remover ${group.label}`}
                      onClick={() => catalog.setDeletingId(group.id)}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                </div>
                {catalog.deletingId === group.id ? (
                  <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-destructive/20 bg-destructive/5 p-3">
                    <p className="text-sm">
                      Remover este grupo? Os usuários deixarão de receber as
                      ofertas dele.
                    </p>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={catalog.busy}
                        onClick={() => catalog.setDeletingId(undefined)}
                      >
                        Cancelar
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        disabled={catalog.busy}
                        onClick={() => void catalog.deleteGroup(group)}
                      >
                        Remover grupo
                      </Button>
                    </div>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="min-w-0 rounded-xl border border-border bg-card p-5 xl:sticky xl:top-0">
        <h2 className="font-semibold">
          {catalog.editingId === undefined
            ? "Adicionar grupo de origem"
            : "Editar grupo de origem"}
        </h2>
        <p className="mt-2 text-sm/6 text-muted-foreground">
          Os usuários podem selecionar os grupos ativos. Ao desativar um grupo,
          o bot para de copiar as ofertas dele.
        </p>
        <form
          className="mt-5 space-y-4"
          onSubmit={(event) => void catalog.submit(event)}
        >
          <fieldset
            disabled={catalog.busy}
            className="space-y-4 disabled:opacity-60"
          >
            <label className="block space-y-2 text-sm font-medium">
              Nome do grupo
              <input
                className={inputClass}
                required
                maxLength={100}
                value={catalog.input.label}
                onChange={(event) =>
                  catalog.setInput((current) => ({
                    ...current,
                    label: event.target.value,
                  }))
                }
                placeholder="Nome para exibir aos usuários"
              />
            </label>
            <label className="block space-y-2 text-sm font-medium">
              Link do Telegram ou @nome_do_grupo
              <input
                className={inputClass}
                required
                value={catalog.input.url}
                onChange={(event) =>
                  catalog.setInput((current) => ({
                    ...current,
                    url: event.target.value,
                  }))
                }
                placeholder="https://t.me/nomedogrupo"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={catalog.input.enabled}
                onChange={(event) =>
                  catalog.setInput((current) => ({
                    ...current,
                    enabled: event.target.checked,
                  }))
                }
              />
              Disponível para os usuários
            </label>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" className="gap-2">
                {catalog.busy ? (
                  <Loader2 className="size-4 animate-spin" />
                ) : (
                  <Plus className="size-4" />
                )}
                {catalog.editingId === undefined
                  ? "Adicionar grupo"
                  : "Salvar alterações"}
              </Button>
              {catalog.editingId !== undefined ? (
                <Button
                  type="button"
                  variant="outline"
                  onClick={catalog.cancelEdit}
                >
                  Cancelar edição
                </Button>
              ) : null}
            </div>
          </fieldset>
        </form>
        {catalog.error ? (
          <p role="alert" className="mt-4 text-sm text-destructive">
            {catalog.error}
          </p>
        ) : null}
        {catalog.notice ? (
          <p role="status" className="mt-4 text-sm/6 text-muted-foreground">
            {catalog.notice}
          </p>
        ) : null}
      </section>
    </div>
  );
}
