export type ConfigSummary = {
  id: number;
  config_type: string;
  config_data?: Record<string, unknown>;
};

export type OfferCategory = "tech" | "home" | "clothes" | "other" | "coupon";

export type DestinationSummary = {
  connection_id?: number | null;
  id: number;
  chat_id: string;
  enabled: boolean;
  title?: string | null;
  chat_type?: string;
  platform?: "telegram" | "whatsapp";
  categories?: OfferCategory[] | null;
};

export type DestinationInput = {
  connection_id?: number | null;
  chat_id: string;
  title: string | null;
  chat_type: string;
  enabled: boolean;
  platform?: "telegram" | "whatsapp";
  categories?: OfferCategory[] | null;
};
