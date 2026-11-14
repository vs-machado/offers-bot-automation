export type GamingPolicy = {
  platforms: Partial<Record<"telegram" | "whatsapp", number>>;
  destinations: Record<string, number>;
};
