"""
Root conftest.py — fixtures compartidos para todo el proyecto.
"""

import pytest
from django.contrib.auth.models import User

from apps.brands.models import Brand, InstagramAccount, Membership
from apps.content.models import ContentBrief, ContentVariant, AgentRun


# ── Users ─────────────────────────────────────────────────────


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="testuser", email="test@example.com", password="testpass123"
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin", email="admin@example.com", password="adminpass123"
    )


# ── Brand ─────────────────────────────────────────────────────


@pytest.fixture
def brand(db):
    return Brand.objects.create(
        name="Test Brand",
        slug="test-brand",
        description="A test brand for unit tests",
        tagline="Testing is caring",
        industry="Technology",
        target_audience="Developers and testers",
        brand_voice_prompt="You are a friendly tech brand.",
        tone_adjectives=["profesional", "cercano", "educativo"],
        tone_description="Friendly and educational",
        forbidden_words=["gratis", "hack"],
        color_primary="#2563EB",
        color_secondary="#1E40AF",
        color_background="#F8FAFC",
        color_accent="#F59E0B",
        color_text="#1E293B",
        default_hashtags=["#testbrand", "#testing"],
        default_language="es",
        preferred_image_style="clean, modern, minimalist",
        preferred_aspect_ratios=["4:5", "1:1"],
    )


@pytest.fixture
def instagram_account(db, brand):
    return InstagramAccount.objects.create(
        brand=brand,
        ig_user_id="17841400000000001",
        username="testbrand_ig",
        access_token="EAAtest123...",
        page_id="100000000000001",
    )


@pytest.fixture
def membership(db, user, brand):
    return Membership.objects.create(
        user=user, brand=brand, role=Membership.Role.EDITOR
    )


# ── Content ───────────────────────────────────────────────────


@pytest.fixture
def brief(db, brand, user):
    return ContentBrief.objects.create(
        brand=brand,
        created_by=user,
        title="5 consejos para mejorar tu código",
        raw_idea="Quiero hacer un post con tips de clean code para devs junior",
        content_type=ContentBrief.ContentType.POST,
        aspect_ratio="4:5",
        num_slides=1,
        priority=3,
    )


@pytest.fixture
def carousel_brief(db, brand, user):
    return ContentBrief.objects.create(
        brand=brand,
        created_by=user,
        title="Guía completa de testing en Python",
        raw_idea="Carrusel educativo sobre pytest, fixtures, mocks y CI/CD",
        content_type=ContentBrief.ContentType.CAROUSEL,
        aspect_ratio="4:5",
        num_slides=7,
        priority=2,
    )


@pytest.fixture
def reel_brief(db, brand, user):
    return ContentBrief.objects.create(
        brand=brand,
        created_by=user,
        title="3 errores que cometes con Git",
        raw_idea="Reel corto mostrando errores comunes de Git y cómo resolverlos",
        content_type=ContentBrief.ContentType.REEL,
        aspect_ratio="9:16",
        num_slides=1,
        priority=5,
    )


@pytest.fixture
def variant(db, brief):
    return ContentVariant.objects.create(
        brief=brief,
        version=1,
        caption="Test caption for the post",
        hashtags=["#python", "#cleancode", "#testing"],
        alt_text="A graphic about clean code tips",
    )


@pytest.fixture
def enriched_brief(db, brief):
    brief.enriched_brief = {
        "tema": "Clean code para desarrolladores junior",
        "angulo": "Errores comunes y cómo evitarlos",
        "objetivo": "Educar y generar engagement",
        "formato_sugerido": "post",
        "num_slides_sugerido": 1,
        "hooks": [
            "El 90% de los devs junior cometen estos errores",
            "Tu código tiene estos 5 problemas (y no lo sabes)",
            "Deja de escribir código espagueti con estos tips",
        ],
        "puntos_clave": [
            "Nombres descriptivos de variables",
            "Funciones cortas y con un solo propósito",
            "Evitar comentarios obvios",
        ],
        "cta": "Guarda este post para cuando lo necesites",
        "keywords": ["clean code", "junior developer", "best practices"],
        "tono_especifico": "Cercano y educativo, como un mentor",
        "referencia_visual": "Fondo oscuro con código resaltado, estilo terminal",
        "audiencia_objetivo": "Desarrolladores junior, 20-30 años",
    }
    brief.status = ContentBrief.Status.READY
    brief.save()
    return brief


# ── Mock providers ────────────────────────────────────────────


@pytest.fixture
def mock_text_response():
    """Respuesta mock de TextProvider.generate()."""
    from apps.integrations.base import TextGenerationResponse

    return TextGenerationResponse(
        text='{"tema": "test", "angulo": "test angle"}',
        model="gpt-4o-mini",
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.0001,
        raw_response={},
    )


@pytest.fixture
def mock_image_response():
    """Respuesta mock de ImageProvider.generate()."""
    from apps.integrations.base import ImageGenerationResponse

    return ImageGenerationResponse(
        image_urls=["https://example.com/generated-image.jpg"],
        model="gpt-image-1",
        cost_usd=0.04,
        raw_response={},
    )
