import type { OfferCategory } from "@/shared/contracts/user-config";

export type WhatsAppStatus = { status: string; name: string | null };
export type WhatsAppConnectionSummary = { id: number; name: string; is_default: boolean };
export type WhatsAppChat = { id: string; name: string };

export type ManagedWhatsAppChat = WhatsAppChat & {
  chat_type: "group" | "channel";
  member_count: number | null;
  capacity: number | null;
  capacity_reported: boolean;
  is_full: boolean | null;
  can_manage: boolean;
  destination_id: number | null;
  categories: OfferCategory[] | null;
  enabled: boolean;
  description?: string;
  admins_only?: boolean | null;
  suggested_name?: string;
};

export type WhatsAppGroupDraft = {
  name: string;
  description: string;
  admins_only: boolean;
  photo: string | null;
  categories: OfferCategory[] | null;
  enabled: boolean;
};

export type WhatsAppGroupCreate = WhatsAppGroupDraft & {
  source_id: string | null;
  reuse_photo: boolean;
  request_id: string;
};

export type WhatsAppGroupResult = {
  id: string;
  name: string;
  enabled: boolean;
  categories: OfferCategory[] | null;
  warnings: string[];
};

export type WhatsAppGroupEditor = {
  chat: ManagedWhatsAppChat | null;
  mode: "create" | "edit";
  requestId: string;
};

export type WhatsAppPolicy = {
  ttl_seconds: number;
  account_interval_seconds: number;
  account_interval_max_seconds: number | null;
  channel_interval_seconds: number;
  max_per_hour: number;
  max_per_day: number;
  destination_max_per_day: number | null;
  max_groups: number;
  posting_timezone: string;
  burst_window_seconds: number;
  burst_threshold: number;
  start_hour_utc: number;
  end_hour_utc: number;
};

export type WhatsAppPolicyData = {
  settings: WhatsAppPolicy;
  burst_keep: number;
  effective_ttl_seconds: number;
  pauses: { chat_id: string | null; paused_until: string; reason_message: string }[];
};
