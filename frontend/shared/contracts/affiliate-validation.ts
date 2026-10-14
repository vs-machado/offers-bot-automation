export type CredentialValidationResult = {
  provider: "amazon" | "mercado_livre" | "shopee" | "aliexpress";
  status: "valid" | "invalid" | "inconclusive";
  reason: string;
  message: string;
  checked_at: string;
};
