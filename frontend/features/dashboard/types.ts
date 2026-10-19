export type DashboardUser = {
  email: string;
  full_name?: string | null;
  role: "user" | "admin";
};

export type DeliveryStatus = "queued" | "retrying" | "sending" | "sent" | "failed" | "expired" | "cancelled" | "uncertain";

export type Delivery = {
  id: string;
  offer_id: string;
  title: string | null;
  price: string | null;
  platform: string | null;
  chat_id: string;
  destination_title: string | null;
  status: DeliveryStatus;
  reason_message: string | null;
  stage: string;
  attempts: number;
  created_at: string;
  updated_at: string;
};

export type Publication = {
  id: string;
  deliveries: Delivery[];
};

export type DeliveryHistoryData = {
  items: Delivery[];
  total: number;
  counts: Partial<Record<DeliveryStatus, number>>;
};
