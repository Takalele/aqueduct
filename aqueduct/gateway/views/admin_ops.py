# aqueduct/gateway/views/admin_ops.py
import logging

from django.core.handlers.asgi import ASGIRequest
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from gateway.authentication import token_from_request
from gateway.config import get_openai_client, get_router, get_router_config
from management.models import Token

log = logging.getLogger("aqueduct")


@csrf_exempt
@require_http_methods(["POST"])
async def reload_router_config(request: ASGIRequest) -> JsonResponse:
    token_key = token_from_request(request)
    if not token_key:
        return JsonResponse({"error": "Authorization header missing"}, status=401)

    token = (
        await Token.objects.select_related("user")
        .filter(key_hash=Token._hash_key(token_key))
        .afirst()
    )

    if not token or not token.user.is_staff:
        return JsonResponse({"error": "Admin token required"}, status=403)

    get_router_config.cache_clear()
    get_router.cache_clear()
    get_openai_client.cache_clear()
    log.info("Router config cache cleared by user %s", token.user.email)

    try:
        new_config = get_router_config()
        return JsonResponse({"status": "ok", "models_loaded": len(new_config["model_list"])})
    except Exception as e:
        log.exception("Failed to reload router config: %s", e)
        return JsonResponse({"status": "error", "detail": str(e)}, status=500)
