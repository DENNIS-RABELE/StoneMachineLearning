import json
import os
from decimal import Decimal, ROUND_HALF_UP

import httpx
import redis
from django.db import transaction
from redis.exceptions import RedisError

from Generator.models import BetOdds


DRN_KEYS = ("drn1", "drn2", "drn3", "drn4", "drn5")
FLT_KEYS = ("flt1", "flt2", "flt3", "flt4", "flt5")
COMBO_KEYS = (
    "flt1_and_drn2",
    "flt1_and_drn3",
    "flt1_and_drn4",
    "flt1_and_drn5",
    "flt2_and_drn3",
    "flt2_and_drn4",
    "flt2_and_drn5",
    "flt3_and_drn4",
    "flt3_and_drn5",
    "flt4_and_drn5",
)

COMBO_PAIRS = {
    "flt1_and_drn2": ("flt1", "drn2"),
    "flt1_and_drn3": ("flt1", "drn3"),
    "flt1_and_drn4": ("flt1", "drn4"),
    "flt1_and_drn5": ("flt1", "drn5"),
    "flt2_and_drn3": ("flt2", "drn3"),
    "flt2_and_drn4": ("flt2", "drn4"),
    "flt2_and_drn5": ("flt2", "drn5"),
    "flt3_and_drn4": ("flt3", "drn4"),
    "flt3_and_drn5": ("flt3", "drn5"),
    "flt4_and_drn5": ("flt4", "drn5"),
}

ONE = Decimal("1")
ZERO = Decimal("0")
HOUSE_EDGE = Decimal("0.125")
OVERROUND_FACTOR = ONE + HOUSE_EDGE
EXPOSURE_ALPHA = Decimal("0.35")
MIN_PROBABILITY = Decimal("0.0001")
MIN_ODDS = Decimal("1.01")
MAX_ODDS = Decimal("99.99")
ODDS_QUANT = Decimal("0.01")

REDIS_URL = os.getenv(
    "BETS_REDIS_URL",
    os.getenv("REDIS_URL", os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")),
)
REDIS_BETS_KEY = os.getenv("REDIS_BETS_KEY", "round:current:bets")


def _url_from_hostport(hostport: str, path: str = "") -> str:
    normalized_hostport = str(hostport or "").strip()
    if not normalized_hostport:
        return ""
    normalized_path = str(path or "").strip()
    if normalized_path and not normalized_path.startswith("/"):
        normalized_path = f"/{normalized_path}"
    return f"http://{normalized_hostport}{normalized_path}"


def _to_decimal(value):
    return Decimal(str(value))


def _normalize_probabilities(probabilities):
    total = sum(probabilities.values(), ZERO)
    if total <= ZERO:
        equal = ONE / _to_decimal(len(probabilities))
        return {key: equal for key in probabilities}
    return {key: probabilities[key] / total for key in probabilities}


def _apply_exposure_shift(probabilities, exposure_stakes, keys, alpha=EXPOSURE_ALPHA):
    market_total_stake = sum(_to_decimal(exposure_stakes.get(key, 0)) for key in keys)
    if market_total_stake <= ZERO:
        return probabilities

    shifted = {}
    for key in keys:
        base_probability = probabilities[key]
        outcome_stake = _to_decimal(exposure_stakes.get(key, 0))
        shifted[key] = base_probability * (ONE + alpha * (outcome_stake / market_total_stake))

    return _normalize_probabilities(shifted)


def _apply_overround(probabilities, overround_factor=OVERROUND_FACTOR):
    return {key: probabilities[key] * overround_factor for key in probabilities}


def _decimal_odds_from_probability(probability):
    safe_probability = max(probability, MIN_PROBABILITY)
    odds = ONE / safe_probability
    odds = min(max(odds, MIN_ODDS), MAX_ODDS)
    return odds.quantize(ODDS_QUANT, rounding=ROUND_HALF_UP)


def _normalize_selection_key(value):
    if not isinstance(value, str):
        return ""

    normalized = value.strip().lower()
    normalized = normalized.replace("&", "_and_")
    normalized = normalized.replace(" and ", "_and_")
    normalized = normalized.replace("-", "_").replace(" ", "_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized


def _extract_stake(row):
    if not isinstance(row, dict):
        return ZERO

    stake_value = row.get("stake", ZERO)
    try:
        stake = _to_decimal(stake_value)
    except Exception:
        return ZERO
    return stake if stake > ZERO else ZERO


def _decode_payload(value):
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")

    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {"value": value}

    return value


def _get_latest_bets(limit=None):
    try:
        client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        key_type = client.type(REDIS_BETS_KEY)

        if key_type == "none":
            return []

        if key_type == "stream":
            items = client.xrevrange(REDIS_BETS_KEY) if limit is None else client.xrevrange(REDIS_BETS_KEY, count=limit)
            items.reverse()
            return [{"redis_id": item_id, **fields} for item_id, fields in items]

        if key_type == "hash":
            items = client.hgetall(REDIS_BETS_KEY)
            parsed = []
            for selection, stake in items.items():
                try:
                    numeric_stake = float(stake)
                except (TypeError, ValueError):
                    numeric_stake = stake
                parsed.append({"selection": selection, "stake": numeric_stake})
            parsed.sort(
                key=lambda row: row["stake"] if isinstance(row["stake"], (int, float)) else -1,
                reverse=True,
            )
            return parsed if limit is None else parsed[:limit]

        if key_type == "list":
            end_index = -1 if limit is None else max(0, limit - 1)
            items = client.lrange(REDIS_BETS_KEY, 0, end_index)
            return [_decode_payload(item) for item in items]

        if key_type == "zset":
            end_index = -1 if limit is None else max(0, limit - 1)
            items = client.zrevrange(REDIS_BETS_KEY, 0, end_index, withscores=True)
            return [{"payload": _decode_payload(payload), "score": score} for payload, score in items]

        if key_type == "string":
            value = client.get(REDIS_BETS_KEY)
            if value is None:
                return []
            decoded = _decode_payload(value)
            if isinstance(decoded, list):
                return decoded if limit is None else decoded[:limit]
            return [decoded]
    except RedisError:
        return []

    return []


def _read_exposure_stakes():
    stakes = {key: ZERO for key in (*DRN_KEYS, *FLT_KEYS, *COMBO_KEYS)}

    for row in _get_latest_bets(limit=None):
        if not isinstance(row, dict):
            continue

        candidates = [row]
        payload = row.get("payload")
        if isinstance(payload, dict):
            candidates.append(payload)

        for candidate in candidates:
            selection = _normalize_selection_key(candidate.get("selection", ""))
            if selection not in stakes:
                continue
            stakes[selection] += _extract_stake(candidate)

    return stakes


def _character_skill_score(character):
    stamina = _to_decimal(character["stamina"]) / Decimal("10")
    control = _to_decimal(character["control"]) / Decimal("10")
    power = _to_decimal(character["power"]) / Decimal("10")
    return (stamina * Decimal("0.35")) + (control * Decimal("0.30")) + (power * Decimal("0.35"))


def _build_true_drn_probabilities(character):
    skill = _character_skill_score(character)

    p_high = Decimal("0.15") + Decimal("0.55") * skill
    p_low = Decimal("0.15") + Decimal("0.55") * (ONE - skill)
    p_mid = max(ZERO, ONE - p_high - p_low)
    state_probabilities = _normalize_probabilities({"high": p_high, "mid": p_mid, "low": p_low})

    conditional_by_state = {
        "high": {
            "drn1": Decimal("0.10"),
            "drn2": Decimal("0.14"),
            "drn3": Decimal("0.19"),
            "drn4": Decimal("0.24"),
            "drn5": Decimal("0.33"),
        },
        "mid": {
            "drn1": Decimal("0.20"),
            "drn2": Decimal("0.20"),
            "drn3": Decimal("0.20"),
            "drn4": Decimal("0.20"),
            "drn5": Decimal("0.20"),
        },
        "low": {
            "drn1": Decimal("0.33"),
            "drn2": Decimal("0.24"),
            "drn3": Decimal("0.19"),
            "drn4": Decimal("0.14"),
            "drn5": Decimal("0.10"),
        },
    }

    probabilities = {}
    for drn_key in DRN_KEYS:
        probability = ZERO
        for state_name, state_probability in state_probabilities.items():
            probability += conditional_by_state[state_name][drn_key] * state_probability
        probabilities[drn_key] = probability

    return _normalize_probabilities(probabilities)


def _build_true_flt_probabilities(drn_probabilities):
    flt_raw = {}
    for i, flt_key in enumerate(FLT_KEYS, start=1):
        drn_key = f"drn{i}"
        flt_raw[flt_key] = ONE - drn_probabilities[drn_key]
    return _normalize_probabilities(flt_raw)


def _build_true_combo_probabilities(flt_probabilities, drn_probabilities):
    combo_probabilities = {}
    for combo_key, (flt_key, drn_key) in COMBO_PAIRS.items():
        combo_probabilities[combo_key] = flt_probabilities[flt_key] * drn_probabilities[drn_key]
    return _normalize_probabilities(combo_probabilities)


def generate_odd_payload(character, exposure_stakes=None):
    if exposure_stakes is None:
        exposure_stakes = _read_exposure_stakes()

    drn_true = _build_true_drn_probabilities(character)
    drn_true = _apply_exposure_shift(drn_true, exposure_stakes, DRN_KEYS)

    flt_true = _build_true_flt_probabilities(drn_true)
    flt_true = _apply_exposure_shift(flt_true, exposure_stakes, FLT_KEYS)

    combo_true = _build_true_combo_probabilities(flt_true, drn_true)
    combo_true = _apply_exposure_shift(combo_true, exposure_stakes, COMBO_KEYS)

    drn_implied = _apply_overround(drn_true)
    flt_implied = _apply_overround(flt_true)
    combo_implied = _apply_overround(combo_true)

    payload = {}
    for key in DRN_KEYS:
        payload[key] = _decimal_odds_from_probability(drn_implied[key])
    for key in FLT_KEYS:
        payload[key] = _decimal_odds_from_probability(flt_implied[key])
    for key in COMBO_KEYS:
        payload[key] = _decimal_odds_from_probability(combo_implied[key])

    return payload


def _build_decision_gateway_url(base_url: str, path: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/api"):
        normalized = f"{normalized}/gateway/decision"
    elif normalized.endswith("/api/gateway"):
        normalized = f"{normalized}/decision"
    elif normalized.endswith("/api/decision") or normalized.endswith("/api/gateway/decision"):
        pass
    return f"{normalized}/{path.lstrip('/')}"


def _build_character_feed_urls():
    urls = []
    decision_service_url = os.getenv("DECISION_SERVICE_URL", "").strip()
    decision_service_hostport = os.getenv("DECISION_SERVICE_HOSTPORT", "").strip()
    render_port = os.getenv("PORT", "").strip()

    # Fetch characters directly from decision_service (not through admin_portal gateway)
    if decision_service_url:
        urls.append(f"{decision_service_url.rstrip('/')}/api/characters/latest/")
    elif decision_service_hostport:
        urls.append(_url_from_hostport(decision_service_hostport, "/api/characters/latest/"))
    elif render_port:
        urls.append(f"http://127.0.0.1:{render_port}/api/characters/latest/")
    else:
        urls.append("http://decision_service:9000/api/characters/latest/")
        urls.append("http://127.0.0.1:9000/api/characters/latest/")

    # Preserve order while dropping duplicates.
    deduped = []
    seen = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped


def _fetch_latest_characters(params):
    with httpx.Client(timeout=10.0) as client:
        for url in _build_character_feed_urls():
            try:
                response = client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                characters = payload.get("results") or []
                if characters:
                    return characters
            except Exception:
                continue
    return []


def sync_latest_character_odds(limit: int = 5, character_ids=None):
    params = {"limit": max(1, limit)}
    if character_ids:
        params["ids"] = ",".join(str(cid) for cid in character_ids)

    characters = _fetch_latest_characters(params)

    if not characters:
        return {"processed": 0, "character_ids": [], "character_names": []}

    seen = set()
    latest_characters = []
    for character in characters:
        character_id = character.get("id")
        if character_id in seen:
            continue
        seen.add(character_id)
        latest_characters.append(character)
        if len(latest_characters) >= max(1, limit):
            break

    exposure_stakes = _read_exposure_stakes()
    latest_ids = [character["id"] for character in latest_characters]

    with transaction.atomic():
        BetOdds.objects.exclude(character_id__in=latest_ids).delete()
        for character in latest_characters:
            BetOdds.objects.update_or_create(
                character_id=character["id"],
                defaults=generate_odd_payload(character=character, exposure_stakes=exposure_stakes),
            )

    return {
        "processed": len(latest_ids),
        "character_ids": latest_ids,
        "character_names": [character["name"] for character in latest_characters],
    }
