from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from Generator.services import sync_latest_character_odds


def _parse_character_ids(raw_value):
    if not raw_value:
        return None
    result = []
    for item in str(raw_value).split(","):
        item = item.strip()
        if not item or not item.isdigit():
            continue
        value = int(item)
        if value > 0:
            result.append(value)
    return result or None


@require_http_methods(["GET", "POST"])
def sync_latest_odds_view(request):
    limit_raw = (
        request.POST.get("limit")
        if request.method == "POST"
        else request.GET.get("limit")
    )
    ids_raw = (
        request.POST.get("character_ids")
        if request.method == "POST"
        else request.GET.get("character_ids")
    )
    limit = int(limit_raw) if str(limit_raw or "").isdigit() else 5
    character_ids = _parse_character_ids(ids_raw)
    result = sync_latest_character_odds(limit=max(1, limit), character_ids=character_ids)
    return JsonResponse(result)
