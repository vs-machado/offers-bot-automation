"use client";

import { Select } from "@base-ui/react/select";
import { useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

type SelectFieldProps = {
  id: string;
  value: string;
  options: { value: string; label: string }[];
  onValueChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
};

/** Theme-aware Base UI select with native keyboard and focus management. */
export function SelectField({
  id,
  value,
  options,
  onValueChange,
  disabled,
  className,
  "aria-label": ariaLabel,
}: SelectFieldProps) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [portalContainer, setPortalContainer] = useState<HTMLElement>();

  return (
    <Select.Root
      items={options}
      value={value}
      onValueChange={(next) => {
        if (next !== null) onValueChange(next);
      }}
      disabled={disabled}
      onOpenChange={(open) => {
        // Keep options inside the accessibility boundary of custom dialogs.
        if (open) {
          setPortalContainer(
            triggerRef.current?.closest<HTMLElement>('[role="dialog"]') ?? undefined,
          );
        }
      }}
    >
      <Select.Trigger
        ref={triggerRef}
        id={id}
        aria-label={ariaLabel}
        data-slot="select-trigger"
        className={cn(
          "flex h-11 w-full min-w-0 items-center justify-between gap-2 rounded-lg border border-input bg-background px-3 text-base text-foreground outline-none transition-colors focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 motion-reduce:transition-none sm:text-sm",
          className,
        )}
      >
        <Select.Value className="truncate" />
        <Select.Icon>
          <ChevronDown
            aria-hidden="true"
            className="size-4 shrink-0 text-muted-foreground"
          />
        </Select.Icon>
      </Select.Trigger>
      <Select.Portal container={portalContainer}>
        <Select.Positioner
          sideOffset={8}
          align="start"
          alignItemWithTrigger={false}
          className="z-50 outline-none"
        >
          <Select.Popup
            data-slot="select-content"
            className="max-h-[min(var(--available-height),24rem)] w-(--anchor-width) min-w-40 overflow-y-auto rounded-xl border bg-popover p-1 text-popover-foreground shadow-md outline-none"
          >
            <Select.List>
              {options.map((option) => (
                <Select.Item
                  key={option.value}
                  value={option.value}
                  className="relative flex min-h-11 cursor-default items-center gap-2 rounded-lg py-2 pl-3 pr-9 text-sm outline-none select-none data-highlighted:bg-accent data-highlighted:text-accent-foreground"
                >
                  <Select.ItemText>{option.label}</Select.ItemText>
                  <Select.ItemIndicator className="absolute right-3">
                    <Check aria-hidden="true" className="size-4" />
                  </Select.ItemIndicator>
                </Select.Item>
              ))}
            </Select.List>
          </Select.Popup>
        </Select.Positioner>
      </Select.Portal>
    </Select.Root>
  );
}
