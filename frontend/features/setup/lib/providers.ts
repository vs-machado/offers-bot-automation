import type { ConfigSummary } from "@/shared/contracts/user-config";

export type ProviderType = "amazon" | "shopee" | "mercado_livre" | "aliexpress";

export type ProviderField = {
  key: string;
  label: string;
  placeholder?: string;
  required?: boolean;
};

export type Provider = {
  type: ProviderType;
  name: string;
  description: string;
  fields: ProviderField[];
};

export function getExistingConfig(
  configs: ConfigSummary[],
  providerType: ProviderType
) {
  return configs.find((config) => config.config_type === providerType);
}

export function getProviderData(
  provider: Provider,
  configs: ConfigSummary[]
): Record<string, string> {
  const existingConfig = getExistingConfig(configs, provider.type);

  return provider.fields.reduce<Record<string, string>>((data, field) => {
    const value = existingConfig?.config_data?.[field.key];
    data[field.key] = typeof value === "string" ? value : "";
    return data;
  }, {});
}
