"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getRecentXPosts } from "../api/x-buffer-client";
import type { RecentXPosts } from "../api/x-buffer-types";

const postDate = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short", timeZone: "America/Sao_Paulo" });

export function RecentXPostsPanel({ settingsVersion }: { settingsVersion: number }) {
  const [refresh, setRefresh] = useState(0);
  const [result, setResult] = useState<{ settingsVersion: number; refresh: number; data?: RecentXPosts; error?: string }>();
  const current = result?.settingsVersion === settingsVersion && result.refresh === refresh ? result : undefined;

  useEffect(() => {
    const controller = new AbortController();
    void getRecentXPosts(controller.signal).then((data) => {
      if (!controller.signal.aborted) setResult({ settingsVersion, refresh, data });
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ settingsVersion, refresh, error: "Não foi possível carregar as publicações. Tente atualizar." });
    });
    return () => controller.abort();
  }, [refresh, settingsVersion]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Últimas publicações</CardTitle>
        <CardDescription>Enviadas ao X pelo Buffer.</CardDescription>
        <CardAction>
          <Button type="button" size="icon" variant="ghost" aria-label="Atualizar publicações" disabled={!current} onClick={() => setRefresh((count) => count + 1)}>
            <RefreshCw aria-hidden="true" className="size-4" />
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent aria-busy={!current}>
        {!current && <p role="status" className="text-muted-foreground">Carregando publicações…</p>}
        {current?.error && <p role="alert" className="text-muted-foreground">{current.error}</p>}
        {current?.data && (
          current.data.posts.length ? (
            <ul className="divide-y">
              {current.data.posts.map((post) => (
                <li key={post.id} className="grid gap-2 py-3 first:pt-0 last:pb-0">
                  <p className="line-clamp-4 wrap-anywhere whitespace-pre-line">{post.text || "Publicação sem texto"}</p>
                  <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                    {post.sent_at && Number.isFinite(Date.parse(post.sent_at)) && <time dateTime={post.sent_at} className="text-muted-foreground">{postDate.format(new Date(post.sent_at))}</time>}
                    {post.url && <a href={post.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-primary hover:underline">Ver no X <ArrowUpRight aria-hidden="true" className="size-3.5" /></a>}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="rounded-xl border border-dashed p-4 text-muted-foreground">{current.data.configured ? "Nenhuma publicação enviada pelo Buffer." : "Salve a chave e o canal do Buffer para ver as publicações."}</p>
          )
        )}
      </CardContent>
    </Card>
  );
}
