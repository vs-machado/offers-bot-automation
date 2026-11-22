import { useId, useState } from "react";
import { SelectField } from "@/components/ui/select";
import type { AvailableSource } from "@/features/settings/types";

type SourceBlacklistEditorProps = {
  sources: AvailableSource[];
  drafts: Record<string, string>;
  onChange: (source: string, draft: string) => void;
  disabled: boolean;
};

export function SourceBlacklistEditor({ sources, drafts, onChange, disabled }: SourceBlacklistEditorProps) {
  const id = useId();
  const [preferredSource, setPreferredSource] = useState("");
  const source = sources.find(({ url }) => url === preferredSource) ?? sources[0];

  return (
    <section aria-labelledby={`${id}-title`} className="space-y-3 rounded-xl border p-4">
      <div className="space-y-1">
        <h3 id={`${id}-title`} className="text-sm font-semibold">Blacklist por origem</h3>
        <p className="text-sm text-muted-foreground">
          O bot ignora ofertas cujo título contém uma palavra ou frase da lista daquele grupo.
        </p>
      </div>
      {source ? (
        <div className="grid items-start gap-4 md:grid-cols-2">
          <div className="min-w-0 space-y-2">
            <label htmlFor={`${id}-source`} className="block text-sm font-medium">Grupo de origem</label>
            <SelectField
              id={`${id}-source`}
              value={source.url}
              options={sources.map(({ url, label }) => ({ value: url, label }))}
              onValueChange={setPreferredSource}
              disabled={disabled}
            />
          </div>
          <div className="min-w-0 space-y-2">
            <label htmlFor={`${id}-terms`} className="block text-sm font-medium">Termos bloqueados</label>
            <textarea
              id={`${id}-terms`}
              aria-describedby={`${id}-hint`}
              className="block w-full rounded-lg border border-input bg-background p-3 text-base focus-visible:outline-2 focus-visible:outline-ring disabled:opacity-50 sm:text-sm"
              rows={3}
              placeholder={"sacos\npapel toalha"}
              value={drafts[source.url] ?? ""}
              onChange={(event) => onChange(source.url, event.target.value)}
              disabled={disabled}
            />
            <p id={`${id}-hint`} className="text-xs text-muted-foreground">
              Um termo por linha, até 50 por grupo e 80 caracteres por termo. Acentos e maiúsculas não fazem diferença.
            </p>
          </div>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">Selecione um grupo acima para configurar a blacklist.</p>
      )}
    </section>
  );
}
