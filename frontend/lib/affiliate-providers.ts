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

export const affiliateProviders: Provider[] = [
  {
    type: "amazon",
    name: "Amazon",
    description: "Informe sua tag de afiliado Amazon.",
    fields: [
      { key: "amazon_affiliate_tag", label: "Tag de afiliado", placeholder: "suatag-20", required: true },
    ],
  },
  {
    type: "shopee",
    name: "Shopee",
    description: "Informe as credenciais do seu programa de afiliados na Shopee Open Platform.",
    fields: [
      { key: "shopee_app_id", label: "ID do aplicativo", required: true },
      { key: "shopee_app_secret", label: "Chave secreta do aplicativo", required: true },
    ],
  },
  {
    type: "mercado_livre",
    name: "Mercado Livre",
    description: "Informe sua tag de afiliado, os cookies da sessão e o token CSRF do Mercado Livre.",
    fields: [
      { key: "ml_affiliate_tag", label: "Tag de afiliado", required: true },
      { key: "ml_cookie_header", label: "Cookies da sessão", required: true },
      { key: "ml_csrf_token", label: "Token CSRF", required: true },
    ],
  },
  {
    type: "aliexpress",
    name: "AliExpress",
    description: "Informe as credenciais do AliExpress e, se tiver, seu ID de rastreamento.",
    fields: [
      { key: "aliexpress_app_key", label: "Chave do aplicativo", required: true },
      { key: "aliexpress_app_secret", label: "Chave secreta do aplicativo", required: true },
      { key: "aliexpress_tracking_id", label: "ID de rastreamento", placeholder: "default" },
    ],
  },
];
