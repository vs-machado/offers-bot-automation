const fieldNames: Record<string, string> = {
  email: "e-mail", password: "senha", full_name: "nome completo",
  label: "nome do grupo", url: "link do Telegram", chat_id: "ID do grupo ou canal",
};

export function getApiErrorMessage(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object" || !("detail" in data)) return fallback;
  const detail = data.detail;
  if (typeof detail === "string") {
    if (detail === "Not authenticated") return "Entre na sua conta para continuar.";
    if (detail.startsWith("Telegram Bot API")) return "Não foi possível publicar no Telegram. Confira as permissões do bot no grupo ou canal.";
    if (detail.startsWith("TELEGRAM_BOT_TOKEN")) return "O bot da plataforma não está configurado. Entre em contato com o administrador.";
    return detail;
  }
  if (Array.isArray(detail)) {
    const error = detail[0] as { loc?: unknown[]; type?: string; msg?: string; ctx?: { min_length?: number; max_length?: number } } | undefined;
    const field = String(error?.loc?.at(-1) ?? "");
    const name = fieldNames[field] ?? "campo";
    if (field === "email") return "Confira se o e-mail foi digitado corretamente.";
    if (error?.type === "missing") return `Preencha o campo ${name}.`;
    if (error?.type === "string_too_short") {
      const minimum = error.ctx?.min_length ?? 1;
      return minimum === 1 ? `Preencha o campo ${name}.` : `O campo ${name} precisa ter pelo menos ${minimum} caracteres.`;
    }
    if (error?.type === "string_too_long") return `O campo ${name} deve ter no máximo ${error.ctx?.max_length ?? 100} caracteres.`;
    // Custom validators in our API return Brazilian Portuguese; Pydantic adds this prefix.
    if (error?.type === "value_error" && ["password", "url"].includes(field) && error.msg) {
      return error.msg.replace(/^Value error, /, "");
    }
    return fallback;
  }
  if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") return detail.message;
  return fallback;
}

export function getRequestErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof TypeError) return "Não foi possível conectar. Confira sua conexão e tente novamente.";
  return error instanceof Error ? error.message : fallback;
}
