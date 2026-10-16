"use client";

import Image from "next/image";
import { Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LinkedText } from "@/features/source-groups/components/LinkedText";
import {
  MessagePreviewSkeleton,
  SourceGroupsSkeleton,
} from "@/features/source-groups/components/SourcePreviewSkeletons";
import { TelegramPostEmbed } from "@/features/source-groups/components/TelegramPostEmbed";
import { useSourceGroupPreviews } from "@/features/source-groups/hooks/use-source-group-previews";
import {
  getHiddenMessageLinks,
  getSourceDisplayLabel,
} from "@/features/source-groups/lib/source-messages";
import { getTelegramPostId } from "@/features/source-groups/lib/telegram";

type SourceGroupsProps = {
  selectedSources: string[];
  onSelectionChange: (sources: string[]) => void;
  catalog?: { url: string; label: string }[];
  onCatalogLoad?: (sourceIds: string[]) => void;
  disabled?: boolean;
};

/** Shared catalog picker and real conversation previews; persistence stays with the caller. */
export function SourceGroups({
  selectedSources,
  onSelectionChange,
  catalog,
  onCatalogLoad,
  disabled = false,
}: SourceGroupsProps) {
  const previews = useSourceGroupPreviews({ enabled: true, catalog, onCatalogLoad });

  return (
    <div className="grid min-h-0 gap-4 lg:grid-cols-[minmax(220px,300px)_minmax(0,1fr)]">
      <section aria-label="Grupos de origem" className="min-w-0 overflow-hidden rounded-2xl border bg-muted/25">
        <div className="border-b p-4">
          <p className="text-sm font-bold">Grupos de origem</p>
          <p className="mt-1 text-xs/5 text-muted-foreground">Confira as mensagens e marque os grupos que quer acompanhar.</p>
          <p className="mt-2 text-xs font-bold text-primary">{selectedSources.length} selecionados</p>
        </div>
        <div className="max-h-60 space-y-1 overflow-y-auto p-2 lg:max-h-[min(60dvh,640px)]">
          {previews.sourceGroupsLoading && !catalog ? <SourceGroupsSkeleton /> : previews.sourceGroups.map((group) => {
            const selected = selectedSources.includes(group.id);
            const active = previews.activeSourceGroup?.id === group.id;
            const label = getSourceDisplayLabel(group);
            return (
              <div key={group.id} className={`flex items-center gap-2 rounded-xl border p-2 ${active ? "border-primary/30 bg-primary/10" : "border-transparent hover:bg-background/70"}`}>
                <button
                  type="button"
                  aria-pressed={active}
                  disabled={disabled}
                  onClick={() => previews.selectSourceGroup(group.id)}
                  className="min-w-0 flex-1 rounded-lg p-2 text-left text-sm font-bold wrap-anywhere focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
                >
                  {label}
                </button>
                <button
                  type="button"
                  aria-label={selected ? `Remover ${label}` : `Selecionar ${label}`}
                  aria-pressed={selected}
                  disabled={disabled}
                  onClick={() => {
                    previews.selectSourceGroup(group.id);
                    onSelectionChange(selected
                      ? selectedSources.filter((id) => id !== group.id)
                      : [...selectedSources, group.id]);
                  }}
                  className={`flex size-9 shrink-0 items-center justify-center rounded-full border focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 ${selected ? "border-primary bg-primary text-primary-foreground" : "border-border bg-background"}`}
                >
                  {selected ? <Check className="size-4" /> : null}
                </button>
              </div>
            );
          })}
          {!previews.sourceGroupsLoading && !previews.sourceGroups.length ? <p className="p-3 text-sm text-muted-foreground">Nenhum grupo de origem está disponível no momento.</p> : null}
        </div>
      </section>
      <section aria-label={previews.activeSourceGroup ? `Mensagens de ${getSourceDisplayLabel(previews.activeSourceGroup)}` : "Mensagens recentes"} className="min-w-0 overflow-hidden rounded-2xl border bg-muted/25">
        {previews.error ? (
          <div role="alert" className="space-y-3 border-b p-4 text-sm text-destructive">
            <p>{previews.error}</p>
            <Button type="button" variant="outline" onClick={previews.retry} disabled={disabled}>
              Tentar novamente
            </Button>
          </div>
        ) : null}
        <div className="relative h-[min(60dvh,640px)] min-h-64 overflow-hidden">
          {previews.sourceGroupsLoading ? <div role="status" aria-label="Carregando mensagens" className="p-4"><MessagePreviewSkeleton /></div> : null}
          {!previews.sourceGroupsLoading && !previews.sourceGroups.length ? <p className="p-5 text-sm text-muted-foreground">Nenhuma conversa disponível para visualizar.</p> : null}
          {!previews.sourceGroupsLoading ? previews.sourceGroups.filter((group) => previews.mountedSourceGroupIds.includes(group.id) || group.id === previews.activeSourceGroup?.id).map((group) => {
            const active = group.id === previews.activeSourceGroup?.id;
            const messages = group.messages ?? [];
            const waiting = messages.some((message) => {
              const postId = getTelegramPostId(message.post_url);
              return postId && !previews.readyTelegramPostIds.includes(postId);
            });
            return (
              <div key={group.id} aria-hidden={!active} inert={!active} className={`absolute inset-0 overflow-y-auto p-4 ${active ? "opacity-100" : "pointer-events-none opacity-0"}`}>
                {active && waiting ? <MessagePreviewSkeleton count={messages.length} /> : null}
                <div aria-busy={active && waiting} inert={active && waiting} className={active && waiting ? "absolute inset-x-4 top-4 space-y-3 opacity-0" : "space-y-3"}>
                  {messages.map((message) => {
                    const postId = getTelegramPostId(message.post_url);
                    if (postId) {
                      return (
                        <div key={message.id}>
                          <TelegramPostEmbed postId={postId} onReady={previews.markTelegramPostReady} />
                          <a href={message.post_url} target="_blank" rel="noreferrer" className="text-xs text-primary underline">
                            Ver mensagem no Telegram
                          </a>
                        </div>
                      );
                    }
                    const links = getHiddenMessageLinks(message);
                    return (
                      <article key={message.id} className="overflow-hidden rounded-2xl rounded-tl-md bg-background text-sm/6 shadow-sm ring-1 ring-border">
                        {message.image_url ? (
                          <a href={message.post_url ?? message.image_url} target="_blank" rel="noreferrer">
                            <Image
                              alt=""
                              src={message.image_url}
                              width={760}
                              height={520}
                              sizes="(min-width: 1024px) 760px, 100vw"
                              unoptimized
                              className="max-h-90 w-full object-cover"
                            />
                          </a>
                        ) : null}
                        <div className="space-y-3 p-4">
                          <p className="whitespace-pre-wrap wrap-anywhere"><LinkedText text={message.text} /></p>
                          {links.length ? (
                            <div className="flex flex-wrap gap-2">
                              {links.map((link) => (
                                <a key={link.url} href={link.url} target="_blank" rel="noreferrer" className="rounded-full bg-primary/10 px-3 py-1 text-xs text-primary wrap-anywhere">
                                  {link.text ?? link.url}
                                </a>
                              ))}
                            </div>
                          ) : null}
                          {message.post_url ? (
                            <a href={message.post_url} target="_blank" rel="noreferrer" className="text-xs text-primary underline">
                              Ver mensagem no Telegram
                            </a>
                          ) : null}
                        </div>
                      </article>
                    );
                  })}
                  {!messages.length ? <p className="rounded-xl bg-background p-4 text-sm/6 text-muted-foreground">As mensagens recentes não estão disponíveis, mas você ainda pode selecionar este grupo.</p> : null}
                </div>
              </div>
            );
          }) : null}
        </div>
      </section>
    </div>
  );
}
