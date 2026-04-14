"""Management command para cargar la configuración versionada del negocio."""

from collections import Counter
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.brands.models import Brand, InstagramAccount, Membership
from apps.brands.seed import BrandSeedBundle, load_seed_bundles
from apps.content.models import ContentBrief


class Command(BaseCommand):
    help = "Carga la seed versionada del negocio y el backlog inicial de briefs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--seed-dir",
            default=str(settings.BASE_DIR / "seed_data" / "business"),
            help="Directorio raíz donde viven las seeds versionadas.",
        )
        parser.add_argument(
            "--brand",
            dest="brand_slug",
            help="Slug de una marca específica para cargar solo su carpeta.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Ejecuta validaciones y upserts dentro de una transacción revertida.",
        )

    def handle(self, *args, **options):
        seed_dir = Path(options["seed_dir"]).resolve()
        bundles = load_seed_bundles(seed_dir, brand_slug=options.get("brand_slug"))
        summary = Counter()

        with transaction.atomic():
            for bundle in bundles:
                self._apply_bundle(bundle, summary)

            if options["dry_run"]:
                transaction.set_rollback(True)

        self._print_summary(summary, dry_run=options["dry_run"])

    def _apply_bundle(self, bundle: BrandSeedBundle, summary: Counter):
        self.stdout.write(f"Cargando seed para la marca '{bundle.brand['slug']}' desde {bundle.path}")
        brand = self._upsert_brand(bundle.brand, summary)
        users = self._upsert_users(bundle.users, summary)
        self._upsert_memberships(bundle.memberships, brand, users, summary)
        self._upsert_instagram_accounts(bundle.instagram_accounts, brand, summary)
        self._upsert_briefs(bundle.briefs, brand, users, summary)

    def _upsert_brand(self, brand_data: dict, summary: Counter) -> Brand:
        defaults = {key: value for key, value in brand_data.items() if key != "slug"}
        brand, created = Brand.objects.update_or_create(slug=brand_data["slug"], defaults=defaults)
        summary["brands_created" if created else "brands_updated"] += 1
        return brand

    def _upsert_users(self, users_data: list[dict], summary: Counter) -> dict[str, object]:
        user_model = get_user_model()
        users = {}
        for user_data in users_data:
            user, created = user_model.objects.get_or_create(username=user_data["username"])
            user.email = user_data["email"]
            user.first_name = user_data["first_name"]
            user.last_name = user_data["last_name"]
            user.is_staff = user_data["is_staff"]
            user.is_superuser = user_data["is_superuser"]
            user.is_active = user_data["is_active"]
            user.set_password(user_data["password"])
            user.save()
            summary["users_created" if created else "users_updated"] += 1
            users[user.username] = user
        return users

    def _upsert_memberships(self, memberships_data: list[dict], brand: Brand, users: dict[str, object], summary: Counter):
        for membership_data in memberships_data:
            _, created = Membership.objects.update_or_create(
                user=users[membership_data["username"]],
                brand=brand,
                defaults={"role": membership_data["role"]},
            )
            summary["memberships_created" if created else "memberships_updated"] += 1

    def _upsert_instagram_accounts(self, accounts_data: list[dict], brand: Brand, summary: Counter):
        for account_data in accounts_data:
            defaults = {key: value for key, value in account_data.items() if key != "ig_user_id"}
            _, created = InstagramAccount.objects.update_or_create(
                brand=brand,
                ig_user_id=account_data["ig_user_id"],
                defaults=defaults,
            )
            summary["instagram_accounts_created" if created else "instagram_accounts_updated"] += 1

    def _upsert_briefs(self, briefs_data: list[dict], brand: Brand, users: dict[str, object], summary: Counter):
        for brief_data in briefs_data:
            created_by = None
            if brief_data["created_by_username"]:
                created_by = users[brief_data["created_by_username"]]

            defaults = {
                "title": brief_data["title"],
                "raw_idea": brief_data["raw_idea"],
                "content_type": brief_data["content_type"],
                "aspect_ratio": brief_data["aspect_ratio"],
                "num_slides": brief_data["num_slides"],
                "status": brief_data["status"],
                "scheduled_for": brief_data["scheduled_for"],
                "tags": brief_data["tags"],
                "priority": brief_data["priority"],
                "created_by": created_by,
            }
            _, created = ContentBrief.objects.update_or_create(
                brand=brand,
                seed_key=brief_data["seed_key"],
                defaults=defaults,
            )
            summary["briefs_created" if created else "briefs_updated"] += 1

    def _print_summary(self, summary: Counter, dry_run: bool):
        self.stdout.write(self.style.SUCCESS("Seed procesada correctamente."))
        if dry_run:
            self.stdout.write(self.style.WARNING("Dry-run activo: no se persistieron cambios."))

        for key in sorted(summary):
            self.stdout.write(f"- {key}: {summary[key]}")