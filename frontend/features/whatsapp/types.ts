export type WhatsAppStatus = { status: string; name: string | null };
export type WhatsAppChat = { id: string; name: string };

export type WhatsAppPolicy = {
  ttl_seconds: number;
  account_interval_seconds: number;
  channel_interval_seconds: number;
  max_per_hour: number;
  max_per_day: number;
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
