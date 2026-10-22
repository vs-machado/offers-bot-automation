"use client";

import { useState } from "react";
import { UsersRound, Megaphone, LockKeyhole, TriangleAlert, Plus, Pencil, Tags, Pause, Play, RefreshCw, Trash2, ArrowRightLeft, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { OfferCategorySelector } from "@/features/offer-routing/OfferCategorySelector";
import type { ManagedWhatsAppChat, WhatsAppConnectionSummary } from "@/features/whatsapp/types";
import type { OfferCategory } from "@/shared/contracts/user-config";

const categoryLabels: Record<OfferCategory, string> = { tech: "Tecnologia", home: "Casa", clothes: "Roupas e acessórios", other: "Outros", coupon: "Cupons" };

export function WhatsAppChatCard({ chat, disabled, connected, onEdit, onNext, onRefresh, onRouting, onRemove, otherConnections, onMove }: {
  chat: ManagedWhatsAppChat;
  disabled: boolean;
  connected: boolean;
  onEdit: () => void;
  onNext: () => void;
  onRefresh: () => void;
  onRouting: (categories: OfferCategory[] | null, enabled: boolean) => Promise<void>;
  onRemove: () => Promise<void>;
  otherConnections: WhatsAppConnectionSummary[];
  onMove: (id: number) => Promise<void>;
}) {
  const [showRouting, setShowRouting] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [categories, setCategories] = useState(chat.categories);
  const [targetId, setTargetId] = useState("");
  const isGroup = chat.chat_type === "group";
  const Icon = isGroup ? UsersRound : Megaphone;
  const percentage = chat.member_count !== null && chat.capacity ? Math.min(100, chat.member_count / chat.capacity * 100) : null;
  const tags = chat.categories === null ? ["Todas as categorias"] : chat.categories.length ? chat.categories.map((category) => categoryLabels[category]) : ["Sem ofertas"];

  return <article className={`flex min-w-0 flex-col gap-4 rounded-2xl border bg-card p-5 ${chat.is_full ? "border-amber-500/70" : ""}`}>
    <div className="flex items-start gap-3">
      <div className="rounded-xl bg-muted p-3"><Icon className="size-5" aria-hidden="true" /></div>
      <div className="min-w-0 flex-1">
        <h3 className="wrap-anywhere font-semibold">{chat.name}</h3>
        <p className="mt-1 text-xs text-muted-foreground">{isGroup ? "Grupo" : "Canal"} · {chat.destination_id == null ? "Não cadastrado" : chat.enabled ? "Publicações ativas" : "Publicações desativadas"}</p>
      </div>
    </div>
    <div className="space-y-2">
      <p className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <span>{chat.member_count === null ? "Quantidade indisponível" : `${chat.member_count.toLocaleString("pt-BR")}${chat.capacity ? ` / ${chat.capacity.toLocaleString("pt-BR")}` : ""} ${isGroup ? "membros" : "seguidores"}`}</span>
        {chat.is_full ? <span className="flex items-center gap-1 font-semibold text-amber-700 dark:text-amber-400"><TriangleAlert className="size-4" aria-hidden="true" />Lotado</span> : null}
      </p>
      {percentage !== null ? <div role="progressbar" aria-label={`Lotação de ${chat.name}`} aria-valuenow={chat.member_count ?? 0} aria-valuemin={0} aria-valuemax={Math.max(chat.capacity ?? 0, chat.member_count ?? 0)} className="h-2 overflow-hidden rounded-full bg-muted"><div className={`h-full rounded-full ${chat.is_full ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${percentage}%` }} /></div> : null}
      {isGroup && chat.capacity && !chat.capacity_reported ? <p className="text-xs text-muted-foreground">Referência: limite padrão de {chat.capacity.toLocaleString("pt-BR")} membros; WAHA não informou limite específico.</p> : null}
      {!isGroup ? <p className="text-xs text-muted-foreground">Canais não usam limite de membros dos grupos.</p> : null}
      {isGroup && chat.admins_only ? <p className="flex items-center gap-1 text-xs text-muted-foreground"><LockKeyhole className="size-3" aria-hidden="true" />Mensagens somente de administradores</p> : null}
    </div>
    <div className="flex flex-wrap gap-1.5" aria-label="Categorias de ofertas">{tags.map((tag) => <span key={tag} className="rounded-full bg-muted px-2.5 py-1 text-xs">{tag}</span>)}</div>
    <div className="mt-auto flex flex-wrap gap-2">
      {isGroup ? <>
        <Button variant={chat.is_full ? "default" : "outline"} disabled={disabled || !connected || !chat.can_manage} onClick={onNext}><Plus aria-hidden="true" />Criar próximo grupo</Button>
        <Button variant="outline" disabled={disabled || !connected || !chat.can_manage} onClick={onEdit}><Pencil aria-hidden="true" />Editar grupo</Button>
      </> : null}
      <Button variant="outline" disabled={disabled || !connected} onClick={() => { setCategories(chat.categories); setShowRouting(!showRouting); }} aria-expanded={showRouting}><Tags aria-hidden="true" />Categorias</Button>
      <Button variant="outline" disabled={disabled || !connected} onClick={() => void onRouting(chat.categories, !chat.enabled)}>{chat.enabled ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}{chat.enabled ? "Pausar ofertas" : "Ativar ofertas"}</Button>
      <Button variant="ghost" disabled={disabled || !connected} onClick={onRefresh}><RefreshCw aria-hidden="true" />Atualizar {isGroup ? "membros" : "seguidores"}</Button>
      {chat.destination_id != null ? <Button variant="destructive-outline" disabled={disabled} onClick={() => setConfirmRemove(true)}><Trash2 aria-hidden="true" />Remover destino</Button> : null}
    </div>
    {chat.destination_id != null && otherConnections.length ? <div className="space-y-2 border-t pt-3">
      <label className="block space-y-2 text-sm">Transferir para outra conta
        <select className="h-10 w-full rounded-lg border bg-background px-3" disabled={disabled} value={targetId} onChange={(event) => setTargetId(event.target.value)}>
          <option value="">Selecione uma conexão</option>
          {otherConnections.map((connection) => <option key={connection.id} value={connection.id}>{connection.name}</option>)}
        </select>
      </label>
      <p className="text-xs/relaxed text-muted-foreground">Troca somente a conta usada pelo Offers Bot para enviar ofertas a este destino. Não transfere a propriedade do grupo ou canal no WhatsApp nem adiciona o novo número. Adicione a nova conta ao destino e confirme permissões de administrador antes de ativar.</p>
      <p className="text-xs/relaxed text-muted-foreground">A transferência pausa os envios deste destino e cancela publicações pendentes da conta anterior. Depois, selecione a nova conta e clique em Ativar ofertas. Categorias e histórico são preservados.</p>
      <Button variant="outline" disabled={disabled || !targetId} onClick={() => void onMove(Number(targetId))}><ArrowRightLeft aria-hidden="true" />Transferir e pausar publicações</Button>
    </div> : null}
    {confirmRemove ? <div className="space-y-3 rounded-lg bg-muted p-3 text-sm">
      <p>Remover este destino? Ofertas deixarão de ser enviadas. O grupo ou canal não será excluído do WhatsApp.</p>
      <div className="flex flex-wrap gap-2"><Button variant="destructive-outline" disabled={disabled} onClick={() => void onRemove().then(() => setConfirmRemove(false))}><Trash2 aria-hidden="true" />Confirmar remoção</Button><Button variant="outline" disabled={disabled} onClick={() => setConfirmRemove(false)}><X aria-hidden="true" />Cancelar</Button></div>
    </div> : null}
    {showRouting ? <div className="space-y-3 border-t pt-4">
      <OfferCategorySelector value={categories} onChange={setCategories} disabled={disabled || !connected} />
      <Button disabled={disabled || !connected} onClick={() => void onRouting(categories, chat.enabled)}><Save aria-hidden="true" />Salvar categorias</Button>
    </div> : null}
  </article>;
}
