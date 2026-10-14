import type { ConfigSummary, DestinationSummary } from "@/shared/contracts/user-config";

export type AvailableSource = { url: string; label: string };
export type SettingsData = {
  configs: ConfigSummary[];
  destinations: DestinationSummary[];
  sources: AvailableSource[];
};
export type DestinationInput = {
  chat_id: string;
  title: string | null;
  chat_type: string;
  enabled: boolean;
};
