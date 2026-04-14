"""Carga y valida seed data versionada del negocio."""

import json
from dataclasses import dataclass
from pathlib import Path

from decouple import config
from django.core.management.base import CommandError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.brands.models import Membership
from apps.content.models import ContentBrief


ALLOWED_BRIEF_STATUSES = {
    ContentBrief.Status.DRAFT,
    ContentBrief.Status.READY,
}
ALLOWED_BRIEF_TYPES = {choice[0] for choice in ContentBrief.ContentType.choices}
ALLOWED_MEMBERSHIP_ROLES = {choice[0] for choice in Membership.Role.choices}


@dataclass(frozen=True)
class BrandSeedBundle:
    path: Path
    brand: dict
    users: list[dict]
    memberships: list[dict]
    instagram_accounts: list[dict]
    briefs: list[dict]


def load_seed_bundles(seed_dir: Path, brand_slug: str | None = None) -> list[BrandSeedBundle]:
    """Lee y valida una o varias carpetas de seed data."""
    if not seed_dir.exists() or not seed_dir.is_dir():
        raise CommandError(f"No existe el directorio de seed: {seed_dir}")

    if brand_slug:
        brand_paths = [seed_dir / brand_slug]
    else:
        brand_paths = sorted(path for path in seed_dir.iterdir() if path.is_dir())

    if not brand_paths:
        raise CommandError(f"No se encontraron seeds en {seed_dir}")

    bundles = []
    for brand_path in brand_paths:
        if not brand_path.exists() or not brand_path.is_dir():
            raise CommandError(f"No existe la carpeta de seed para la marca '{brand_path.name}'")
        bundles.append(_load_brand_bundle(brand_path))

    return bundles


def _load_brand_bundle(brand_path: Path) -> BrandSeedBundle:
    brand = _normalize_brand(_read_json_object(brand_path / "brand.json"), brand_path)
    users = _normalize_users(_read_json_list(brand_path / "users.json"), brand_path)
    memberships = _normalize_memberships(
        _read_json_list(brand_path / "memberships.json"),
        brand_path,
        {user["username"] for user in users},
    )

    instagram_accounts_path = brand_path / "instagram_accounts.json"
    instagram_accounts = []
    if instagram_accounts_path.exists():
        instagram_accounts = _normalize_instagram_accounts(
            _read_json_list(instagram_accounts_path),
            brand_path,
        )

    briefs = _normalize_briefs(
        _read_json_list(brand_path / "briefs.json"),
        brand_path,
        {user["username"] for user in users},
    )

    if brand["slug"] != brand_path.name:
        raise CommandError(
            f"El slug '{brand['slug']}' en {brand_path / 'brand.json'} debe coincidir con la carpeta '{brand_path.name}'"
        )

    return BrandSeedBundle(
        path=brand_path,
        brand=brand,
        users=users,
        memberships=memberships,
        instagram_accounts=instagram_accounts,
        briefs=briefs,
    )


def _normalize_brand(data: dict, brand_path: Path) -> dict:
    return {
        "slug": _required_string(data, "slug", brand_path),
        "name": _required_string(data, "name", brand_path),
        "logo_url": _optional_string(data, "logo_url"),
        "description": _optional_string(data, "description"),
        "tagline": _optional_string(data, "tagline"),
        "founder_name": _optional_string(data, "founder_name"),
        "industry": _optional_string(data, "industry"),
        "target_audience": _optional_string(data, "target_audience"),
        "brand_voice_prompt": _optional_string(data, "brand_voice_prompt"),
        "tone_adjectives": _string_list(data, "tone_adjectives", brand_path),
        "tone_description": _optional_string(data, "tone_description"),
        "forbidden_words": _string_list(data, "forbidden_words", brand_path),
        "color_primary": _optional_string(data, "color_primary"),
        "color_secondary": _optional_string(data, "color_secondary"),
        "color_background": _optional_string(data, "color_background"),
        "color_accent": _optional_string(data, "color_accent"),
        "color_text": _optional_string(data, "color_text"),
        "default_hashtags": _string_list(data, "default_hashtags", brand_path),
        "default_language": _optional_string(data, "default_language", default="es"),
        "preferred_image_style": _optional_string(data, "preferred_image_style"),
        "preferred_aspect_ratios": _string_list(data, "preferred_aspect_ratios", brand_path),
        "is_active": _boolean(data, "is_active", brand_path, default=True),
    }


def _normalize_users(users: list[dict], brand_path: Path) -> list[dict]:
    if not users:
        raise CommandError(f"{brand_path / 'users.json'} debe incluir al menos un usuario")

    normalized = []
    usernames = set()
    for index, user in enumerate(users, start=1):
        context = f"{brand_path / 'users.json'}[{index}]"
        username = _required_string(user, "username", context)
        if username in usernames:
            raise CommandError(f"Username duplicado en seed users: {username}")
        usernames.add(username)

        normalized.append(
            {
                "username": username,
                "email": _required_string(user, "email", context),
                "first_name": _optional_string(user, "first_name"),
                "last_name": _optional_string(user, "last_name"),
                "is_staff": _boolean(user, "is_staff", context, default=False),
                "is_superuser": _boolean(user, "is_superuser", context, default=False),
                "is_active": _boolean(user, "is_active", context, default=True),
                "password": _resolve_secret(user, "password", "password_env", context),
            }
        )

    return normalized


def _normalize_memberships(memberships: list[dict], brand_path: Path, usernames: set[str]) -> list[dict]:
    if not memberships:
        raise CommandError(f"{brand_path / 'memberships.json'} debe incluir al menos una membresía")

    normalized = []
    seen = set()
    for index, membership in enumerate(memberships, start=1):
        context = f"{brand_path / 'memberships.json'}[{index}]"
        username = _required_string(membership, "username", context)
        if username not in usernames:
            raise CommandError(f"La membresía referencia un username inexistente: {username}")
        role = _optional_string(membership, "role", default=Membership.Role.EDITOR)
        if role not in ALLOWED_MEMBERSHIP_ROLES:
            raise CommandError(f"Rol inválido en {context}: {role}")
        if username in seen:
            raise CommandError(f"Membresía duplicada para el usuario {username}")
        seen.add(username)
        normalized.append({"username": username, "role": role})

    return normalized


def _normalize_instagram_accounts(accounts: list[dict], brand_path: Path) -> list[dict]:
    normalized = []
    seen_ids = set()
    for index, account in enumerate(accounts, start=1):
        context = f"{brand_path / 'instagram_accounts.json'}[{index}]"
        ig_user_id = _required_string(account, "ig_user_id", context)
        if ig_user_id in seen_ids:
            raise CommandError(f"ig_user_id duplicado en seed: {ig_user_id}")
        seen_ids.add(ig_user_id)

        token_expires_at = _optional_datetime(account, "token_expires_at", context)
        normalized.append(
            {
                "ig_user_id": ig_user_id,
                "username": _required_string(account, "username", context),
                "access_token": _resolve_secret(account, "access_token", "access_token_env", context),
                "page_id": _optional_string(account, "page_id"),
                "token_expires_at": token_expires_at,
                "is_active": _boolean(account, "is_active", context, default=True),
            }
        )

    return normalized


def _normalize_briefs(briefs: list[dict], brand_path: Path, usernames: set[str]) -> list[dict]:
    normalized = []
    seen_seed_keys = set()
    for index, brief in enumerate(briefs, start=1):
        context = f"{brand_path / 'briefs.json'}[{index}]"
        seed_key = _required_string(brief, "seed_key", context)
        if seed_key in seen_seed_keys:
            raise CommandError(f"seed_key duplicado en briefs: {seed_key}")
        seen_seed_keys.add(seed_key)

        content_type = _optional_string(brief, "content_type", default=ContentBrief.ContentType.POST)
        if content_type not in ALLOWED_BRIEF_TYPES:
            raise CommandError(f"Tipo de contenido inválido en {context}: {content_type}")

        status = _optional_string(brief, "status", default=ContentBrief.Status.DRAFT)
        if status not in ALLOWED_BRIEF_STATUSES:
            raise CommandError(
                f"Estado inválido en {context}: {status}. Solo se permiten {sorted(ALLOWED_BRIEF_STATUSES)}"
            )

        num_slides = _integer(brief, "num_slides", context, default=1, minimum=1)
        if content_type == ContentBrief.ContentType.CAROUSEL and num_slides < 2:
            raise CommandError(f"Un carrusel seeded debe tener al menos 2 slides en {context}")
        if content_type != ContentBrief.ContentType.CAROUSEL and num_slides != 1:
            raise CommandError(f"Solo los carruseles pueden tener num_slides distinto de 1 en {context}")

        created_by_username = _optional_string(brief, "created_by_username", default="")
        if created_by_username and created_by_username not in usernames:
            raise CommandError(f"El brief {seed_key} referencia un created_by inexistente: {created_by_username}")

        normalized.append(
            {
                "seed_key": seed_key,
                "title": _required_string(brief, "title", context),
                "raw_idea": _required_string(brief, "raw_idea", context),
                "content_type": content_type,
                "aspect_ratio": _optional_string(brief, "aspect_ratio", default="4:5"),
                "num_slides": num_slides,
                "status": status,
                "scheduled_for": _optional_datetime(brief, "scheduled_for", context),
                "tags": _string_list(brief, "tags", context),
                "priority": _integer(brief, "priority", context, default=5, minimum=1),
                "created_by_username": created_by_username or None,
            }
        )

    return normalized


def _read_json_object(path: Path) -> dict:
    data = _read_json(path)
    if not isinstance(data, dict):
        raise CommandError(f"{path} debe contener un objeto JSON")
    return data


def _read_json_list(path: Path) -> list:
    data = _read_json(path)
    if not isinstance(data, list):
        raise CommandError(f"{path} debe contener una lista JSON")
    return data


def _read_json(path: Path):
    if not path.exists():
        raise CommandError(f"Falta el archivo requerido de seed: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CommandError(f"JSON inválido en {path}: {exc}") from exc


def _required_string(data: dict, key: str, context) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"{context} requiere un string no vacío para '{key}'")
    return value.strip()


def _optional_string(data: dict, key: str, default: str = "") -> str:
    value = data.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise CommandError(f"El campo '{key}' debe ser un string")
    return value.strip()


def _string_list(data: dict, key: str, context) -> list[str]:
    value = data.get(key, [])
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise CommandError(f"{context} requiere una lista de strings para '{key}'")
    return [item.strip() for item in value if item.strip()]


def _boolean(data: dict, key: str, context, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise CommandError(f"{context} requiere un booleano para '{key}'")
    return value


def _integer(data: dict, key: str, context, default: int, minimum: int | None = None) -> int:
    value = data.get(key, default)
    if not isinstance(value, int):
        raise CommandError(f"{context} requiere un entero para '{key}'")
    if minimum is not None and value < minimum:
        raise CommandError(f"{context} requiere que '{key}' sea >= {minimum}")
    return value


def _optional_datetime(data: dict, key: str, context):
    value = data.get(key)
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise CommandError(f"{context} requiere un datetime ISO string para '{key}'")
    parsed = parse_datetime(value)
    if parsed is None:
        raise CommandError(f"No se pudo parsear '{key}' en {context}: {value}")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _resolve_secret(data: dict, direct_key: str, env_key: str, context) -> str:
    direct_value = data.get(direct_key)
    if isinstance(direct_value, str) and direct_value.strip():
        return direct_value.strip()

    env_name = data.get(env_key)
    if not isinstance(env_name, str) or not env_name.strip():
        raise CommandError(
            f"{context} debe definir '{direct_key}' o '{env_key}' para cargar un valor sensible"
        )

    secret_value = config(env_name.strip(), default="")
    if not secret_value:
        raise CommandError(f"Falta la variable de entorno requerida: {env_name}")
    return secret_value