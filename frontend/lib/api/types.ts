export type DashboardUser = {
  email: string;
  full_name?: string | null;
};

export type DestinationSummary = {
  id: number;
  chat_id: string;
  enabled: boolean;
};

export type ConfigSummary = {
  id: number;
  config_type: string;
  config_data?: Record<string, unknown>;
};

export type SourceGroup = {
  id: string;
  label: string;
  messages?: SourceMessage[];
};

export type SourceMessage = {
  id: number;
  text: string;
  image_url?: string;
  post_url?: string;
  links?: Array<{
    text?: string;
    url: string;
  }>;
};
