"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { SelectField } from "@/components/ui/select";
import { saveNvidiaModels } from "@/features/settings/api/nvidia-models-client";
import type { NvidiaCatalog } from "@/features/settings/types";
import type { ConfigSummary } from "@/shared/contracts/user-config";

export function PostingModelForm({ catalog, config }: { catalog: NvidiaCatalog; config?: ConfigSummary }) {
  function available(value: unknown, fallback: string) {
    return typeof value === "string" && Object.hasOwn(catalog.models, value) ? value : fallback;
  }

  const formId = useId();
  const [id, setId] = useState(config?.id);
  const [primary, setPrimary] = useState(available(config?.config_data?.primary, catalog.primary));
  const [secondary, setSecondary] = useState(available(config?.config_data?.secondary, catalog.secondary));
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");
  const options = Object.entries(catalog.models).map(([value, label]) => ({ value, label }));
  const hasDuplicateModels = primary === secondary;

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSaving || hasDuplicateModels) return;
    setIsSaving(true);
    setMessage("");
    try {
      const saved = await saveNvidiaModels(primary, secondary, id);
      setId(saved.id);
      setMessage("Modelos salvos.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Não foi possível salvar os modelos.");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Card className="max-w-3xl">
      <CardHeader>
        <CardTitle>Modelos de publicação</CardTitle>
        <CardDescription>
          Se o modelo primário falhar ou demorar demais, o bot usa o secundário.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form onSubmit={save} className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            {([
              ["primary", "Modelo primário", primary, setPrimary],
              ["secondary", "Modelo secundário", secondary, setSecondary],
            ] as const).map(([field, label, value, setValue]) => {
              const fieldId = `${formId}-${field}`;
              return (
                <div key={field} className="min-w-0 space-y-2">
                  <label htmlFor={fieldId} className="block text-sm font-medium">
                    {label}
                  </label>
                  <SelectField
                    id={fieldId}
                    value={value}
                    options={options}
                    disabled={isSaving}
                    onValueChange={(next) => {
                      setValue(next);
                      setMessage("");
                    }}
                  />
                </div>
              );
            })}
          </div>
          <p className="text-sm text-muted-foreground">
            Modelo secundário recomendado: {catalog.models[catalog.secondary]}.
          </p>
          <Button type="submit" disabled={isSaving || hasDuplicateModels}>
            {isSaving ? "Salvando…" : "Salvar modelos"}
          </Button>
          {hasDuplicateModels && <p role="status" className="text-sm">Selecione dois modelos diferentes.</p>}
          {message && <p role="status" className="text-sm">{message}</p>}
        </form>
      </CardContent>
    </Card>
  );
}
