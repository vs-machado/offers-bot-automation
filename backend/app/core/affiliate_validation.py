"""Local Amazon tag validation and bounded probes for other affiliate providers."""

import asyncio
from datetime import datetime, timezone
import hashlib
import hmac
import json
import re
import time
from urllib.parse import urlparse

import httpx
from backend.app.core.magalu import (
    MagaluClient,
    MagaluError,
    SAMPLE_PRODUCT_URL,
    valid_config,
)
from backend.app.core.awin import (
    KABUM_ADVERTISER_ID,
    is_tracking_link,
    link_endpoint,
    valid_credentials,
)

from backend.app.schemas.affiliate_validation import (
    CredentialValidationRequest,
    CredentialValidationResult,
)

REQUIRED = {
    "amazon": ("amazon_affiliate_tag",),
    "mercado_livre": ("ml_affiliate_tag", "ml_cookie_header", "ml_csrf_token"),
    "shopee": ("shopee_app_id", "shopee_app_secret"),
    "aliexpress": ("aliexpress_app_key", "aliexpress_app_secret"),
    "awin": ("awin_publisher_id", "awin_access_token"),
    "magalu": ("magalu_partner_id", "magalu_promoter_id", "magalu_store_name"),
}
MESSAGES = {
    "locally_valid": "Configuração Amazon válida localmente: o formato da tag está correto. Esta verificação não autentica sua conta nem confirma a existência ou titularidade da tag. Salve a configuração para usar no bot.",
    "invalid_amazon_tag": "Informe somente a tag de associado Amazon, com letras, números ou hífens e sufixo de dois dígitos, como minhaloja-20 (máximo de 100 caracteres). Não informe um link completo.",
    "validated": "A loja aceitou a geração de um link com os dados informados. O acesso foi validado neste momento. Salve as credenciais para usar essa configuração no bot.",
    "missing_fields": "Preencha todos os campos obrigatórios da loja antes de validar.",
    "invalid_format": "Há um campo com formato inválido ou muito longo. Confira os dados e copie novamente as credenciais.",
    "authentication": "A loja recusou a autenticação. A sessão pode ter expirado; copie novamente os cookies e, no Mercado Livre, o token CSRF.",
    "api_key": "A loja recusou a chave de API ou a assinatura. Confira o ID ou a chave do aplicativo e sua chave secreta.",
    "permission": "A loja informou que essa conta não tem permissão para gerar o link. Confira o acesso ao programa de afiliados.",
    "blocked": "A loja bloqueou a requisição ou pediu uma verificação adicional. Não foi possível confirmar as credenciais; isso não significa que estejam inválidas.",
    "rate_limit": "A loja limitou as requisições. Aguarde alguns minutos e valide novamente.",
    "timeout": "A loja demorou para responder. A validação ficou inconclusiva; tente novamente mais tarde.",
    "connection": "Não foi possível conectar à loja. Tente novamente mais tarde.",
    "api_unavailable": "A API da loja está indisponível ou retornou uma resposta inesperada. Não foi possível confirmar as credenciais.",
    "product_url": "Para validar o Mercado Livre, informe o link completo de um produto dessa loja, incluindo o ID MLB. Links curtos não são aceitos nesta verificação.",
    "link_not_generated": "A loja respondeu, mas não gerou o link de validação. O produto pode não participar do programa ou a API pode ter mudado. Não foi possível confirmar as credenciais.",
    "busy": "Já existe uma validação em andamento ou o serviço está ocupado. Aguarde alguns segundos e tente novamente.",
}
_slots = asyncio.Semaphore(8)
_active_users: set[int] = set()


class ProbeFailure(Exception):
    def __init__(self, reason: str, invalid: bool = False):
        self.reason = reason
        self.invalid = invalid
        super().__init__(reason)


def outcome(
    provider, reason: str, status: str = "inconclusive"
) -> CredentialValidationResult:
    return CredentialValidationResult(
        provider=provider,
        status=status,
        reason=reason,
        message=MESSAGES[reason],
        checked_at=datetime.now(timezone.utc),
    )


def check_response(response: httpx.Response, provider: str) -> dict:
    """Recognize explicit credential rejection; challenge pages remain inconclusive."""
    if 300 <= response.status_code < 400:
        location = response.headers.get("location", "").lower()
        login = any(token in location for token in ("signin", "login", "auth/"))
        raise ProbeFailure("authentication" if login else "blocked", invalid=login)
    if response.status_code == 401:
        raise ProbeFailure(
            "api_key" if provider in ("shopee", "aliexpress") else "authentication",
            invalid=True,
        )
    if response.status_code == 429:
        raise ProbeFailure("rate_limit")
    if response.status_code >= 500:
        raise ProbeFailure("api_unavailable")
    try:
        data = response.json()
    except ValueError:
        raise ProbeFailure(
            "blocked"
            if response.status_code == 403 or "captcha" in response.text.lower()
            else "api_unavailable"
        ) from None
    if not isinstance(data, dict):
        raise ProbeFailure("api_unavailable")
    # Inspect only error fields internally; raw response text is never returned.
    errors = data.get("errors") or data.get("error_response") or data.get("error")
    if not errors and isinstance(data.get("urls"), list):
        errors = [
            item
            for item in data["urls"]
            if isinstance(item, dict) and item.get("error_code") not in (None, 0, "0")
        ]
    if errors or response.status_code >= 400 or data.get("code") not in (None, 0, "0"):
        text = json.dumps(
            errors or {key: data.get(key) for key in ("message", "msg", "code")}
        ).lower()
        if any(token in text for token in ("captcha", "robot", "challenge")):
            raise ProbeFailure("blocked")
        if any(
            token in text
            for token in (
                "too many requests",
                "rate limit",
                "ratelimit",
                "quota exceeded",
            )
        ):
            raise ProbeFailure("rate_limit")
        if any(
            token in text
            for token in (
                "invalid api key",
                "invalid app key",
                "invalid appkey",
                "invalidappkey",
                "invalidapikey",
                "invalidappsecret",
                "invalid signature",
                "invalidsignature",
                "invalid application",
                "invalid app secret",
                "incomplete signature",
                "incompletesignature",
                "invalidsign",
                "invalidcredential",
            )
        ):
            raise ProbeFailure("api_key", invalid=True)
        if any(
            token in text
            for token in (
                "unauthorized",
                "authentication failed",
                "session expired",
                "login required",
                "invalid csrf",
                "csrf token",
            )
        ):
            raise ProbeFailure("authentication", invalid=True)
        if any(
            token in text
            for token in (
                "permission denied",
                "insufficient permission",
                "not authorized",
            )
        ):
            raise ProbeFailure("permission", invalid=True)
        raise ProbeFailure(
            "blocked" if response.status_code == 403 else "api_unavailable"
        )
    return data


def require_link(value, domains: tuple[str, ...]) -> None:
    if not isinstance(value, str):
        raise ProbeFailure("link_not_generated")
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in domains:
        raise ProbeFailure("link_not_generated")


def amazon_tag_reason(value: object) -> str:
    """Check tag syntax locally, without verifying existence or account ownership."""
    if value is None or isinstance(value, str) and not value.strip():
        return "missing_fields"
    if (
        not isinstance(value, str)
        or len(value.strip()) > 100
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*-[0-9]{2}", value.strip())
    ):
        return "invalid_amazon_tag"
    return "locally_valid"


async def probe(
    client: httpx.AsyncClient,
    provider: str,
    values: dict[str, str],
    product_url: str | None,
) -> None:
    """Generate one verification link without visiting user URLs or fetching images."""
    if provider == "mercado_livre":
        parsed = urlparse(product_url or "")
        if (
            parsed.scheme != "https"
            or parsed.hostname
            not in (
                "www.mercadolivre.com.br",
                "mercadolivre.com.br",
                "produto.mercadolivre.com.br",
            )
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise ProbeFailure("product_url")
        ids = list(
            dict.fromkeys(
                match.upper().replace("-", "")
                for match in re.findall(
                    r"MLB-?\d{6,}", parsed.path + "?" + parsed.query, re.IGNORECASE
                )
            )
        )
        if not ids:
            raise ProbeFailure("product_url")
        response = await client.post(
            "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink",
            headers={
                "cookie": values["ml_cookie_header"],
                "x-csrf-token": values["ml_csrf_token"],
                "origin": "https://www.mercadolivre.com.br",
                "referer": "https://www.mercadolivre.com.br/afiliados/hub",
            },
            json={
                "itemId": ids[0],
                "itemAddToList": ids[-1],
                "tag": values["ml_affiliate_tag"],
                "type": "product",
                "urls": [product_url.removeprefix("https://")],
                "extraCommission": "false",
            },
        )
        data = check_response(response, provider)
        links = data.get("urls")
        link = (
            links[0].get("short_url")
            if isinstance(links, list) and links and isinstance(links[0], dict)
            else None
        )
        require_link(
            link,
            (
                "meli.la",
                "mercadolivre.com",
                "www.mercadolivre.com",
                "mercadolivre.com.br",
                "www.mercadolivre.com.br",
            ),
        )
    elif provider == "awin":
        response = await client.post(
            link_endpoint(values["awin_publisher_id"]),
            headers={"Authorization": f"Bearer {values['awin_access_token']}"},
            json={
                "advertiserId": KABUM_ADVERTISER_ID,
                "destinationUrl": "https://www.kabum.com.br/",
                "shorten": True,
            },
        )
        data = check_response(response, provider)
        if not is_tracking_link(data.get("url")) or (
            data.get("shortUrl") and not is_tracking_link(data["shortUrl"])
        ):
            raise ProbeFailure("link_not_generated")
    elif provider == "shopee":
        query = "mutation generateShortLink($input: ShortLinkInput!) { generateShortLink(input: $input) { shortLink } }"
        body = json.dumps(
            {
                "query": query,
                "variables": {"input": {"originUrl": "https://shopee.com.br/"}},
                "operationName": None,
            },
            separators=(",", ":"),
        )
        timestamp = int(time.time())
        signature = hashlib.sha256(
            f"{values['shopee_app_id']}{timestamp}{body}{values['shopee_app_secret']}".encode()
        ).hexdigest()
        response = await client.post(
            "https://open-api.affiliate.shopee.com.br/graphql",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"SHA256 Credential={values['shopee_app_id']},Timestamp={timestamp},Signature={signature}",
            },
            content=body,
        )
        data = check_response(response, provider)
        link = data.get("data", {}).get("generateShortLink", {}).get("shortLink")
        require_link(link, ("s.shopee.com.br", "shope.ee", "shopee.com.br"))
    else:
        params = {
            "app_key": values["aliexpress_app_key"],
            "sign_method": "sha256",
            "timestamp": str(int(round(time.time()))) + "000",
            "partner_id": "iop-sdk-python-20220609",
            "method": "aliexpress.affiliate.link.generate",
            "simplify": "false",
            "format": "json",
            "ship_to_country": "BR",
            "promotion_link_type": "0",
            "source_values": "https://www.aliexpress.com",
            "tracking_id": values.get("aliexpress_tracking_id") or "default",
        }
        signed = "".join(f"{key}{params[key]}" for key in sorted(params))
        params["sign"] = (
            hmac.new(
                values["aliexpress_app_secret"].encode(),
                signed.encode(),
                hashlib.sha256,
            )
            .hexdigest()
            .upper()
        )
        response = await client.post("https://api-sg.aliexpress.com/sync", data=params)
        data = check_response(response, provider)
        result = data.get("aliexpress_affiliate_link_generate_response", data).get(
            "resp_result", {}
        )
        links = (
            result.get("result", {})
            .get("promotion_links", {})
            .get("promotion_link", [])
        )
        link = (
            links[0].get("promotion_link")
            if isinstance(links, list) and links and isinstance(links[0], dict)
            else None
        )
        require_link(
            link,
            (
                "s.click.aliexpress.com",
                "www.aliexpress.com",
                "aliexpress.com",
                "pt.aliexpress.com",
            ),
        )


async def validate_credentials(
    request: CredentialValidationRequest, user_id: int
) -> CredentialValidationResult:
    """Check Amazon syntax locally or probe other stores; never save or post drafts."""
    provider = request.provider
    if provider == "amazon":
        tag = request.config_data.get("amazon_affiliate_tag")
        reason = amazon_tag_reason(tag.get_secret_value() if tag is not None else None)
        return outcome(
            provider, reason, "valid" if reason == "locally_valid" else "invalid"
        )
    values = {
        key: value.get_secret_value().strip()
        for key, value in request.config_data.items()
    }
    if any(not values.get(key) for key in REQUIRED[provider]):
        return outcome(provider, "missing_fields", "invalid")
    if provider == "magalu" and not valid_config(
        values["magalu_partner_id"],
        values["magalu_promoter_id"],
        values["magalu_store_name"],
    ):
        return outcome(provider, "invalid_format", "invalid")
    if provider == "awin" and not valid_credentials(
        values["awin_publisher_id"], values["awin_access_token"]
    ):
        return outcome(provider, "invalid_format", "invalid")
    if any(
        len(value) > 65536 or "\r" in value or "\n" in value
        for value in values.values()
    ):
        return outcome(provider, "invalid_format", "invalid")
    header_keys = (
        "ml_cookie_header",
        "ml_csrf_token",
        "shopee_app_id",
    )
    if any(not values[key].isascii() for key in header_keys if key in values):
        return outcome(provider, "invalid_format", "invalid")
    if user_id in _active_users or _slots.locked():
        return outcome(provider, "busy")
    _active_users.add(user_id)
    try:
        async with _slots, asyncio.timeout(20):
            if provider == "magalu":
                client = MagaluClient(
                    values["magalu_partner_id"],
                    values["magalu_promoter_id"],
                    values["magalu_store_name"],
                    values.get("magalu_utm_campaign", "divulgacao_influencer"),
                )
                await asyncio.to_thread(client.generate, SAMPLE_PRODUCT_URL)
                return outcome(provider, "validated", "valid")
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=False,
                headers={
                    "accept": "application/json",
                    "accept-language": "pt-BR,pt;q=0.9",
                    "user-agent": "Mozilla/5.0",
                },
            ) as client:
                await probe(client, provider, values, request.product_url)
        return outcome(provider, "validated", "valid")
    except ProbeFailure as exc:
        return outcome(
            provider, exc.reason, "invalid" if exc.invalid else "inconclusive"
        )
    except (TimeoutError, httpx.TimeoutException):
        return outcome(provider, "timeout")
    except httpx.RequestError:
        return outcome(provider, "connection")
    except MagaluError as exc:
        cause = exc.__cause__
        if isinstance(cause, httpx.TimeoutException):
            return outcome(provider, "timeout")
        if isinstance(cause, httpx.RequestError):
            return outcome(provider, "connection")
        if isinstance(cause, httpx.HTTPStatusError):
            code = cause.response.status_code
            return outcome(provider, "rate_limit" if code == 429 else "api_unavailable")
        return outcome(provider, "link_not_generated")
    except Exception:
        return outcome(provider, "api_unavailable")
    finally:
        _active_users.discard(user_id)
