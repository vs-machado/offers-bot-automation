export function getAuthError(error: { code?: string; message?: string } | null | undefined, fallback: string): string {
  const messages: Record<string, string> = {
    EMAIL_PASSWORD_SIGN_UP_DISABLED: "Cadastros temporariamente indisponíveis. Entre com uma conta existente.",
    REGISTRATION_DISABLED: "Cadastros temporariamente indisponíveis. Entre com uma conta existente.",
    "signup disabled": "Cadastros temporariamente indisponíveis. Entre com uma conta existente.",
    signup_disabled: "Cadastros temporariamente indisponíveis. Entre com uma conta existente.",
    INVALID_EMAIL_OR_PASSWORD: "E-mail ou senha incorretos.",
    USER_ALREADY_EXISTS_USE_ANOTHER_EMAIL: "Este e-mail já está cadastrado. Entre na sua conta.",
    USER_ALREADY_EXISTS: "Este e-mail já está cadastrado. Entre na sua conta.",
    INVALID_EMAIL: "Confira se o e-mail foi digitado corretamente.",
    INVALID_TOKEN: "Este link expirou ou já foi usado. Solicite um novo link.",
    PASSWORD_TOO_SHORT: "Use uma senha com pelo menos 8 caracteres.",
    PASSWORD_TOO_LONG: "Sua senha ficou muito longa. Reduza a quantidade de caracteres.",
    EMAIL_NOT_VERIFIED: "Confirme seu e-mail antes de entrar.",
    SOCIAL_PROVIDER_NOT_FOUND: "O acesso com Google não está configurado no momento.",
    ACCOUNT_NOT_LINKED: "Entre com a opção que usou para criar sua conta.",
    TOO_MANY_REQUESTS: "Você fez muitas tentativas. Aguarde um minuto e tente novamente.",
  };
  if (error?.code && messages[error.code]) return messages[error.code];
  if (error?.message && /^(Use |Sua senha|Inclua |Essa senha|A recuperação|O e-mail)/.test(error.message)) return error.message;
  return fallback;
}
