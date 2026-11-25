export type BufferSettings = {
  enabled: boolean;
  destination_id: number | null;
  landing_url: string;
  channel_id: string;
  daily_limit: number;
  has_api_key: boolean;
};

export type BufferState = {
  settings: BufferSettings;
  dashboard_managed: boolean;
  destinations: { id: number; title: string | null; chat_id: string; platform: string; user_id: number }[];
  attempts: { attempted_at: string; status: string }[];
};

export type BufferWrite = Omit<BufferSettings, "has_api_key"> & { api_key?: string };

export type RecentXPosts = {
  configured: boolean;
  posts: { id: string; text: string; sent_at: string | null; url: string | null }[];
};
