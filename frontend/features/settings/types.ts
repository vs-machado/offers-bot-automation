import type { ConfigSummary, DestinationSummary } from "@/shared/contracts/user-config";

export type AvailableSource = { url: string; label: string };
export type SettingsSection = "destinations" | "sources" | "affiliates";
export type SettingsData = {
  configs: ConfigSummary[];
  destinations: DestinationSummary[];
  sources: AvailableSource[];
};
export type { DestinationInput } from "@/shared/contracts/user-config";
