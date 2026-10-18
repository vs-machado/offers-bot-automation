"use client";

import type { OfferCategory } from "@/shared/contracts/user-config";

const categories: { value: OfferCategory; label: string }[] = [
  { value: "tech", label: "Tecnologia" },
  { value: "home", label: "Casa" },
  { value: "clothes", label: "Roupas e acessórios" },
  { value: "other", label: "Outros produtos" },
  { value: "coupon", label: "Cupons" },
];

export function OfferCategorySelector({
  value,
  onChange,
  disabled = false,
}: {
  value: OfferCategory[] | null;
  onChange: (value: OfferCategory[] | null) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset disabled={disabled} className="space-y-3 rounded-xl border p-4">
      <legend className="px-1 text-sm font-semibold">Ofertas neste destino</legend>
      <label className="flex items-center gap-2 text-sm font-medium">
        <input
          type="checkbox"
          checked={value === null}
          onChange={(event) => onChange(
            event.target.checked ? null : categories.map((category) => category.value),
          )}
        />
        Todas as ofertas
      </label>
      <div className="grid gap-3 sm:grid-cols-2">
        {categories.map((category) => (
          <label key={category.value} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={value === null || value.includes(category.value)}
              onChange={(event) => {
                const selected = value ?? categories.map((item) => item.value);
                onChange(event.target.checked
                  ? [...selected, category.value]
                  : selected.filter((item) => item !== category.value));
              }}
            />
            {category.label}
          </label>
        ))}
      </div>
      <p className="text-xs/relaxed text-muted-foreground">
        Desmarque uma categoria para bloquear somente neste grupo ou canal.
        Cupons sem produto têm seleção própria; produtos sem categoria entram em Outros produtos.
      </p>
      {value?.length === 0 ? (
        <p className="text-sm font-medium">Nenhuma categoria selecionada: este destino não receberá ofertas.</p>
      ) : null}
    </fieldset>
  );
}
