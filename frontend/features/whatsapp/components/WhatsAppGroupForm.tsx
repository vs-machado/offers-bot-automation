"use client";

import { useRef, useState, type FormEvent } from "react";
import Image from "next/image";
import { Plus, Save, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { OfferCategorySelector } from "@/features/offer-routing/OfferCategorySelector";
import type { WhatsAppGroupDraft, WhatsAppGroupEditor } from "@/features/whatsapp/types";

const inputClass = "w-full rounded-lg border border-input bg-background px-3 py-2 text-base outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function WhatsAppGroupForm({ editor, disabled, onSave, onClose }: {
  editor: WhatsAppGroupEditor;
  disabled: boolean;
  onSave: (draft: WhatsAppGroupDraft, reusePhoto: boolean) => Promise<void>;
  onClose: () => void;
}) {
  const { chat, mode } = editor;
  const [draft, setDraft] = useState<WhatsAppGroupDraft>({
    name: mode === "create" ? chat?.suggested_name ?? "" : chat?.name ?? "",
    description: chat?.description ?? "",
    admins_only: mode === "create" ? true : chat?.admins_only !== false,
    photo: null, categories: chat?.categories ?? null,
    enabled: mode === "create" ? true : chat?.enabled ?? false,
  });
  const [reusePhoto, setReusePhoto] = useState(true);
  const [photoError, setPhotoError] = useState("");
  const [isReadingPhoto, setIsReadingPhoto] = useState(false);
  const photoVersion = useRef(0);

  async function readPhoto(file?: File) {
    const version = ++photoVersion.current;
    setPhotoError("");
    setDraft((current) => ({ ...current, photo: null }));
    if (!file) { setIsReadingPhoto(false); return; }
    if (file.size > 5 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setPhotoError("Envie JPEG, PNG ou WebP de até 5 MB.");
      setIsReadingPhoto(false);
      return;
    }
    setIsReadingPhoto(true);
    try {
      const photo = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result));
        reader.onerror = () => reject(new Error("Não foi possível ler a foto."));
        reader.readAsDataURL(file);
      });
      if (version === photoVersion.current) setDraft((current) => ({ ...current, photo }));
    } catch { if (version === photoVersion.current) setPhotoError("Não foi possível ler a foto."); }
    finally { if (version === photoVersion.current) setIsReadingPhoto(false); }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!disabled && !isReadingPhoto && !photoError) void onSave(draft, reusePhoto);
  }

  return (
    <section className="rounded-2xl border bg-card p-5 sm:p-6" aria-labelledby="group-form-title">
      <form onSubmit={submit} className="space-y-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="group-form-title" className="text-lg font-semibold">{mode === "edit" ? "Editar grupo" : chat ? "Criar próximo grupo" : "Novo grupo"}</h2>
            <p className="mt-1 text-sm text-muted-foreground">{chat && mode === "create" ? `Modelo: ${chat.name}. Descrição, foto e categorias reaproveitadas. Membros não são copiados.` : "Nome, descrição e foto serão salvos no WhatsApp."}</p>
          </div>
          <Button type="button" variant="ghost" disabled={disabled} onClick={onClose}><X aria-hidden="true" />Fechar</Button>
        </div>
        <fieldset disabled={disabled} className="grid gap-5 lg:grid-cols-2">
          <div className="space-y-4">
            <label className="block space-y-2 text-sm font-medium">
              <span>Nome do grupo</span>
              <input autoFocus required maxLength={100} className={inputClass} value={draft.name} placeholder="Meu grupo tech #3" onChange={(event) => setDraft({ ...draft, name: event.target.value })} />
            </label>
            <label className="block space-y-2 text-sm font-medium">
              <span>Descrição</span>
              <textarea rows={5} maxLength={2048} className={inputClass} value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} />
            </label>
            <label className="flex min-h-11 items-center gap-3 text-sm">
              <Checkbox disabled={disabled} checked={draft.admins_only} onCheckedChange={(admins_only) => setDraft({ ...draft, admins_only })} />
              Somente administradores podem enviar mensagens
            </label>
            <p className="text-xs text-muted-foreground">Comentários dos membros desativados por padrão em novos grupos.</p>
          </div>
          <div className="space-y-4">
            <label className="block space-y-2 text-sm font-medium">
              <span>Foto do grupo</span>
              <input type="file" accept="image/jpeg,image/png,image/webp" className={`${inputClass} file:mr-3 file:text-sm`} onChange={(event) => void readPhoto(event.target.files?.[0])} />
            </label>
            <p className="text-xs text-muted-foreground">JPEG, PNG ou WebP, até 5 MB. {mode === "edit" ? "Sem upload, mantém foto atual." : "Foto enviada substitui foto herdada."}</p>
            {photoError ? <p role="alert" className="text-sm text-destructive">{photoError}</p> : null}
            {draft.photo ? <Image unoptimized src={draft.photo} width={96} height={96} alt="Prévia da nova foto do grupo" className="size-24 rounded-xl object-cover" /> : null}
            {mode === "create" && chat ? <label className="flex min-h-11 items-center gap-3 text-sm">
              <Checkbox disabled={disabled || Boolean(draft.photo)} checked={reusePhoto} onCheckedChange={setReusePhoto} />Usar foto do grupo anterior quando não enviar outra
            </label> : null}
            <OfferCategorySelector value={draft.categories} onChange={(categories) => setDraft({ ...draft, categories })} disabled={disabled} />
            <label className="flex min-h-11 items-center gap-3 text-sm">
              <Checkbox disabled={disabled} checked={draft.enabled} onCheckedChange={(enabled) => setDraft({ ...draft, enabled })} />Publicar ofertas neste grupo
            </label>
          </div>
        </fieldset>
        <div className="flex flex-wrap gap-3">
          <Button type="submit" disabled={disabled || isReadingPhoto || Boolean(photoError) || !draft.name.trim()}>{mode === "create" ? <Plus aria-hidden="true" /> : <Save aria-hidden="true" />}{disabled ? "Salvando…" : isReadingPhoto ? "Lendo foto…" : mode === "create" ? "Criar grupo" : "Salvar grupo"}</Button>
          <Button type="button" variant="outline" disabled={disabled} onClick={onClose}><X aria-hidden="true" />Cancelar</Button>
        </div>
      </form>
    </section>
  );
}
