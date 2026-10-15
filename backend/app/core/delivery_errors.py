"""Safe failure codes; never expose provider responses or credentials."""

import httpx

REASONS = {
    "burst_superseded": "Descartada por rajada: foram priorizadas as 5 ofertas mais recentes deste canal.",
    "policy_deadline": "O prazo terminaria antes do próximo envio permitido. A oferta foi descartada.",
    "delivery_throttled": "Aguardando janela de publicação, coleta de rajada ou limite de frequência da conta/canal.",
    "whatsapp_paused": "Envios pausados temporariamente por falhas ou restrição na conta/canal WhatsApp.",
    "whatsapp_authentication": "O WhatsApp/WAHA recusou a autenticação. Confira a conexão e a configuração do serviço.",
    "whatsapp_permission": "A conta WhatsApp não tem permissão para publicar no destino.",
    "whatsapp_destination": "O WhatsApp/WAHA recusou o destino ou a publicação. Confira o canal e a conexão.",
    "whatsapp_rate_limit": "O WhatsApp/WAHA limitou os envios. A conta foi pausada temporariamente.",
    "whatsapp_api": "O serviço WhatsApp falhou durante o envio.",
    "bot_token_missing": "O token do bot não foi configurado. A administração precisa configurar o bot.",
    "bot_authentication": "O Telegram recusou o token do bot. Ele pode estar inválido ou ter sido revogado.",
    "bot_permission": "O bot não tem permissão para publicar nesse grupo ou canal, ou foi removido.",
    "bot_destination": "O Telegram não encontrou o destino ou recusou a mensagem. Confira o grupo e as permissões do bot.",
    "bot_rate_limit": "O Telegram limitou os envios. A postagem não pôde ser concluída dentro do prazo ou das tentativas disponíveis.",
    "telegram_api": "A API do Telegram falhou durante o envio.",
    "connection_failure": "Não foi possível conectar ao serviço. Confira a conexão e tente novamente mais tarde.",
    "delivery_uncertain": "A conexão falhou após o início do envio. Não foi possível confirmar a publicação; ela não será reenviada automaticamente.",
    "affiliate_authentication": "A plataforma de afiliados recusou a autenticação. Confira os cookies ou as credenciais cadastradas.",
    "affiliate_api_key": "A plataforma de afiliados recusou a chave de API ou sua assinatura. Confira a chave e o segredo cadastrados.",
    "affiliate_permission": "As credenciais de afiliado não têm permissão para executar essa operação.",
    "affiliate_rate_limit": "A plataforma de afiliados limitou as requisições. Não foi possível preparar o link.",
    "affiliate_api": "A plataforma de afiliados não conseguiu gerar o link da promoção.",
    "affiliate_credentials_missing": "Faltam credenciais de afiliado para essa loja. Complete a configuração para publicar suas ofertas.",
    "unsupported_offer": "Essa oferta não é compatível com a conversão de links disponível.",
    "processing_failure": "Não foi possível preparar essa promoção para publicação.",
    "broker_unavailable": "O serviço de fila estava indisponível. A promoção não foi agendada para envio.",
    "destination_disabled_or_removed": "O destino foi desativado ou removido antes da publicação.",
    "promotion_expired": "O prazo de publicação terminou. A promoção foi descartada para evitar enviar uma oferta antiga.",
    "sending_interrupted": "O envio não teve confirmação antes do fim do prazo. Confira o grupo; não haverá reenvio automático.",
    "unexpected_delivery_error": "O envio foi interrompido por uma falha inesperada. O resultado não pôde ser confirmado.",
}


def classify_failure(exc: Exception, stage: str, platform: str | None = None) -> str:
    """Classify explicit evidence only; uncertain errors stay generic."""
    code = getattr(exc, "reason_code", None)
    if code in REASONS:
        return code
    status = getattr(exc, "status_code", None)
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
    if stage == "posting":
        if isinstance(
            exc,
            (
                httpx.ReadTimeout,
                httpx.WriteTimeout,
                httpx.ReadError,
                httpx.WriteError,
                httpx.RemoteProtocolError,
            ),
        ):
            return "delivery_uncertain"
        if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout)):
            return "connection_failure"
        if platform == "whatsapp":
            return {
                401: "whatsapp_authentication",
                403: "whatsapp_permission",
                400: "whatsapp_destination",
                404: "whatsapp_destination",
                429: "whatsapp_rate_limit",
            }.get(status, "whatsapp_api")
        return {
            401: "bot_authentication",
            404: "bot_authentication",
            403: "bot_permission",
            400: "bot_destination",
            429: "bot_rate_limit",
        }.get(status, "telegram_api")
    if stage == "affiliate":
        if status == 401 and platform in ("Shopee", "AliExpress"):
            return "affiliate_api_key"
        if status in (401, 403, 429):
            return {
                401: "affiliate_authentication",
                403: "affiliate_permission",
                429: "affiliate_rate_limit",
            }[status]
        if isinstance(exc, httpx.RequestError):
            return "connection_failure"
        message = str(exc).lower()
        if any(
            part in message
            for part in (
                "invalid api key",
                "invalid app key",
                "invalid signature",
                "invalid application",
                "invalid app secret",
            )
        ):
            return "affiliate_api_key"
        if any(
            part in message
            for part in (
                "unauthorized",
                "authentication failed",
                "session expired",
                "login required",
            )
        ):
            return "affiliate_authentication"
        return "affiliate_api"
    return "processing_failure"
