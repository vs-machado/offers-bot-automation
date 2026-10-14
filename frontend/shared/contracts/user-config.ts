export type ConfigSummary = {
  id: number;
  config_type: string;
  config_data?: Record<string, unknown>;
};

export type DestinationSummary = {
  id: number;
  chat_id: string;
  enabled: boolean;
  title?: string | null;
  chat_type?: string;
};
