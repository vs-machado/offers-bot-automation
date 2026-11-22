"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { saveNvidiaModels } from "@/features/dashboard/api/nvidia-models-client";
import type { NvidiaCatalog } from "@/features/dashboard/types";
import type { ConfigSummary } from "@/shared/contracts/user-config";

export function NvidiaModels({ catalog, config }: { catalog: NvidiaCatalog; config?: ConfigSummary }) {
  function available(value: unknown, fallback: string) {
    return typeof value === "string" && Object.hasOwn(catalog.models, value) ? value : fallback;
  }

  const [id, setId] = useState(config?.id);
  const [primary, setPrimary] = useState(available(config?.config_data?.primary, catalog.primary));
  const [secondary, setSecondary] = useState(available(config?.config_data?.secondary, catalog.secondary));
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function save(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (primary === secondary) return;
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
    <Card className="mb-6">
      <CardContent>
        <form onSubmit={save} className="space-y-3">
          <h2 className="font-medium">Modelos de IA para ofertas</h2>
          <p className="text-sm text-muted-foreground">O bot usa o modelo secundário se o primário falhar ou demorar demais. Recomendamos {catalog.models[catalog.secondary]} como secundário.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {([
              ["Modelo primário", primary, setPrimary],
              ["Modelo secundário", secondary, setSecondary],
            ] as const).map(([label, value, setter]) => (
              <label key={label} className="grid gap-1 text-sm font-medium">
                {label}
                <select className="min-h-10 rounded-md border bg-background px-3" value={value} disabled={isSaving} onChange={(event) => { setter(event.target.value); setMessage(""); }}>
                  {Object.entries(catalog.models).map(([model, name]) => <option value={model} key={model}>{name}</option>)}
                </select>
              </label>
            ))}
          </div>
          <Button type="submit" variant="outline" disabled={isSaving || primary === secondary}>{isSaving ? "Salvando…" : "Salvar modelos"}</Button>
          {primary === secondary && <p className="text-sm text-muted-foreground">Selecione dois modelos diferentes.</p>}
          {message && <p role="status" className="text-sm">{message}</p>}
        </form>
      </CardContent>
    </Card>
  );
}
