import type { ConfigSummary } from "@/shared/contracts/user-config";

export type ProviderType = "amazon" | "shopee" | "mercado_livre" | "aliexpress" | "awin" | "magalu";

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
    type: "magalu",
    name: "Magalu",
    description: "Informe os identificadores da sua conta Magazine Você. Links encurtados são expandidos antes da conversão. Modalidade padrão: Lucreator / link direto.",
    fields: [
      { key: "magalu_partner_id", label: "Partner ID", placeholder: "ID do parceiro", required: true },
      { key: "magalu_promoter_id", label: "Promoter ID", placeholder: "Seu ID de divulgador", required: true },
      { key: "magalu_store_name", label: "Store name", placeholder: "Nome da sua loja, sem URL", required: true },
      { key: "magalu_utm_campaign", label: "Campanha UTM", placeholder: "divulgacao_influencer" },
    ],
  },
  {
    type: "awin",
    name: "Awin (KaBuM)",
    description: "Informe suas credenciais Awin para converter links da KaBuM. Sua conta precisa estar aprovada no programa KaBuM (anunciante 17729).",
    fields: [
      { key: "awin_publisher_id", label: "publisherId", placeholder: "Seu ID de afiliado Awin", required: true },
      { key: "awin_access_token", label: "accessToken", placeholder: "Seu token de API Awin", required: true },
    ],
  },
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
