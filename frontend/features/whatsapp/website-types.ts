export type WebsiteSettings = {
  enabled: boolean;
  website_url: string;
  connection_id: number | null;
  template_destination_id: number | null;
  group_name: string;
  description: string;
  entry_limit: number;
  safety_margin: number;
};

export type WebsiteData = {
  settings: WebsiteSettings;
  active_destination_id: number | null;
  pending_destination_id: number | null;
  needs_recovery: boolean;
  member_count: number | null;
  observed_at: string | null;
  entry_path: string | null;
  invite_expires_at: string | null;
  last_error: string | null;
};
