"""Tests para apps.integrations — base dataclasses, providers, registry."""

import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.integrations.base import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    InstagramMediaContainer,
    InstagramPublishResult,
    TextGenerationRequest,
    TextGenerationResponse,
    UploadResult,
    VideoGenerationRequest,
    VideoGenerationResponse,
)


# ── Dataclass tests ──────────────────────────────────────────


class TestTextGenerationRequest:
    def test_defaults(self):
        req = TextGenerationRequest(system_prompt="sys", user_prompt="user")
        assert req.model == "gpt-4o-mini"
        assert req.temperature == 0.7
        assert req.max_tokens == 2000
        assert req.response_format is None

    def test_custom_values(self):
        req = TextGenerationRequest(
            system_prompt="s", user_prompt="u",
            model="gpt-4o", temperature=0.3, response_format="json_object",
        )
        assert req.model == "gpt-4o"
        assert req.response_format == "json_object"


class TestTextGenerationResponse:
    def test_defaults(self):
        resp = TextGenerationResponse(text="Hello")
        assert resp.text == "Hello"
        assert resp.cost_usd == 0.0
        assert resp.raw_response == {}

    def test_with_cost(self):
        resp = TextGenerationResponse(
            text="output", model="gpt-4o-mini",
            prompt_tokens=100, completion_tokens=50, cost_usd=0.0001,
        )
        assert resp.prompt_tokens == 100
        assert resp.cost_usd == 0.0001


class TestImageGenerationRequest:
    def test_defaults(self):
        req = ImageGenerationRequest(prompt="a cat")
        assert req.width == 1080
        assert req.height == 1350
        assert req.output_format == "jpeg"
        assert req.num_images == 1

    def test_custom_dimensions(self):
        req = ImageGenerationRequest(prompt="a cat", width=1080, height=1920)
        assert req.height == 1920


class TestImageGenerationResponse:
    def test_defaults(self):
        resp = ImageGenerationResponse()
        assert resp.image_urls == []
        assert resp.image_bytes == []
        assert resp.cost_usd == 0.0

    def test_with_urls(self):
        resp = ImageGenerationResponse(
            image_urls=["https://a.com/1.jpg", "https://a.com/2.jpg"],
            cost_usd=0.08,
        )
        assert len(resp.image_urls) == 2


class TestVideoGenerationRequest:
    def test_defaults(self):
        req = VideoGenerationRequest()
        assert req.duration_seconds == 15.0
        assert req.width == 1080
        assert req.height == 1920
        assert req.output_format == "mp4"


class TestInstagramDataclasses:
    def test_media_container(self):
        c = InstagramMediaContainer(container_id="123")
        assert c.container_id == "123"
        assert c.status == "IN_PROGRESS"

    def test_publish_result(self):
        r = InstagramPublishResult(media_id="456", permalink="https://ig.com/p/abc")
        assert r.media_id == "456"
        assert r.error == ""

    def test_upload_result(self):
        u = UploadResult(url="https://cdn.com/f.jpg", key="f.jpg", size_bytes=5000)
        assert u.size_bytes == 5000


# ── OpenAI Text Provider ─────────────────────────────────────


class TestOpenAITextProvider:
    @pytest.mark.asyncio
    async def test_generate_calls_openai(self):
        from apps.integrations.providers.openai_text import OpenAITextProvider

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"result": "test"}'
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock(prompt_tokens=50, completion_tokens=30)
        mock_response.model_dump.return_value = {}

        provider = OpenAITextProvider(api_key="sk-test")

        with patch.object(
            provider._client.chat.completions, "create",
            new_callable=AsyncMock, return_value=mock_response,
        ):
            result = await provider.generate(
                TextGenerationRequest(
                    system_prompt="sys", user_prompt="user"
                )
            )

        assert result.text == '{"result": "test"}'
        assert result.model == "gpt-4o-mini"
        assert result.prompt_tokens == 50
        assert result.cost_usd > 0

    @pytest.mark.asyncio
    async def test_generate_json_format(self):
        from apps.integrations.providers.openai_text import OpenAITextProvider

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "{}"
        mock_response.model = "gpt-4o-mini"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model_dump.return_value = {}

        provider = OpenAITextProvider(api_key="sk-test")

        with patch.object(
            provider._client.chat.completions, "create",
            new_callable=AsyncMock, return_value=mock_response,
        ) as mock_create:
            await provider.generate(
                TextGenerationRequest(
                    system_prompt="s", user_prompt="u",
                    response_format="json_object",
                )
            )

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}


# ── OpenAI Image Provider ────────────────────────────────────


class TestOpenAIImageProvider:
    @pytest.mark.asyncio
    async def test_generate_returns_urls(self):
        from apps.integrations.providers.openai_images import OpenAIImageProvider

        mock_img = MagicMock()
        mock_img.url = "https://oaidalleapiprodscus.blob.core.windows.net/img.jpg"

        mock_response = MagicMock()
        mock_response.data = [mock_img]

        provider = OpenAIImageProvider(api_key="sk-test")

        with patch.object(
            provider._client.images, "generate",
            new_callable=AsyncMock, return_value=mock_response,
        ):
            result = await provider.generate(
                ImageGenerationRequest(prompt="a sunset")
            )

        assert len(result.image_urls) == 1
        assert result.image_bytes == []
        assert "blob.core.windows.net" in result.image_urls[0]
        assert result.cost_usd > 0
        assert result.width == 1024
        assert result.height == 1536
        assert result.content_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_generate_decodes_base64_images(self):
        from apps.integrations.providers.openai_images import OpenAIImageProvider

        mock_img = MagicMock()
        mock_img.url = None
        mock_img.b64_json = base64.b64encode(b"image-bytes").decode("ascii")

        mock_response = MagicMock()
        mock_response.data = [mock_img]

        provider = OpenAIImageProvider(api_key="sk-test")

        with patch.object(
            provider._client.images, "generate",
            new_callable=AsyncMock, return_value=mock_response,
        ):
            result = await provider.generate(
                ImageGenerationRequest(prompt="a sunset")
            )

        assert result.image_urls == []
        assert result.image_bytes == [b"image-bytes"]
        assert result.cost_usd > 0
        assert result.content_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_generate_normalizes_unsupported_size(self):
        from apps.integrations.providers.openai_images import OpenAIImageProvider

        mock_response = MagicMock()
        mock_response.data = []

        provider = OpenAIImageProvider(api_key="sk-test")

        with patch.object(
            provider._client.images, "generate",
            new_callable=AsyncMock, return_value=mock_response,
        ) as mock_generate:
            await provider.generate(
                ImageGenerationRequest(prompt="portrait", width=1080, height=1350)
            )

        assert mock_generate.call_args.kwargs["size"] == "1024x1536"
        assert mock_generate.call_args.kwargs["output_format"] == "jpeg"


# ── Meta Instagram Publisher ─────────────────────────────────


class TestMetaInstagramPublisher:
    @pytest.fixture
    def publisher(self):
        from apps.integrations.providers.meta_instagram import MetaInstagramPublisher
        return MetaInstagramPublisher(timeout=5.0)

    def test_headers(self, publisher):
        headers = publisher._headers("my-token")
        assert headers["Authorization"] == "Bearer my-token"

    @pytest.mark.asyncio
    async def test_create_image_container(self, publisher):
        import httpx

        mock_resp = httpx.Response(
            200,
            json={"id": "container_123"},
            request=httpx.Request("POST", "https://graph.facebook.com/v21.0/ig_user_1/media"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await publisher.create_image_container(
                "ig_user_1", "https://cdn.com/img.jpg", "Caption!", "token"
            )

        assert result.container_id == "container_123"

    @pytest.mark.asyncio
    async def test_create_carousel_container(self, publisher):
        import httpx

        mock_resp = httpx.Response(
            200,
            json={"id": "carousel_456"},
            request=httpx.Request("POST", "https://graph.facebook.com/v21.0/ig_user_1/media"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await publisher.create_carousel_container(
                "ig_user_1", ["child_1", "child_2"], "Caption!", "token"
            )

        assert result.container_id == "carousel_456"

    @pytest.mark.asyncio
    async def test_create_reel_container(self, publisher):
        import httpx

        mock_resp = httpx.Response(
            200,
            json={"id": "reel_789"},
            request=httpx.Request("POST", "https://graph.facebook.com/v21.0/ig_user_1/media"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await publisher.create_reel_container(
                "ig_user_1", "https://cdn.com/video.mp4", "Reel caption!", "token"
            )

        assert result.container_id == "reel_789"

    @pytest.mark.asyncio
    async def test_check_container_status(self, publisher):
        import httpx

        mock_resp = httpx.Response(
            200,
            json={"status_code": "FINISHED"},
            request=httpx.Request("GET", "https://graph.facebook.com/v21.0/container_123"),
        )

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            status = await publisher.check_container_status("container_123", "token")

        assert status == "FINISHED"

    @pytest.mark.asyncio
    async def test_publish_container(self, publisher):
        import httpx

        mock_publish = httpx.Response(
            200,
            json={"id": "media_999"},
            request=httpx.Request("POST", "https://graph.facebook.com/v21.0/ig_user_1/media_publish"),
        )
        mock_detail = httpx.Response(
            200,
            json={"permalink": "https://www.instagram.com/p/ABC/"},
            request=httpx.Request("GET", "https://graph.facebook.com/v21.0/media_999"),
        )

        with patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_publish,
        ), patch(
            "httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_detail,
        ):
            result = await publisher.publish_container("ig_user_1", "container_123", "token")

        assert result.media_id == "media_999"
        assert result.permalink == "https://www.instagram.com/p/ABC/"

    @pytest.mark.asyncio
    async def test_create_carousel_child_image(self, publisher):
        import httpx

        mock_resp = httpx.Response(
            200,
            json={"id": "child_001"},
            request=httpx.Request("POST", "https://graph.facebook.com/v21.0/ig_user_1/media"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            result = await publisher.create_carousel_child_image(
                "ig_user_1", "https://cdn.com/slide.jpg", "token"
            )

        assert result.container_id == "child_001"


# ── S3 Storage Provider ──────────────────────────────────────


class TestS3StorageProvider:
    @pytest.mark.asyncio
    async def test_upload_bytes(self, settings):
        settings.AWS_S3_ENDPOINT_URL = "https://s3.example.com"
        settings.AWS_ACCESS_KEY_ID = "test-key"
        settings.AWS_SECRET_ACCESS_KEY = "test-secret"
        settings.AWS_STORAGE_BUCKET_NAME = "test-bucket"
        settings.AWS_S3_CUSTOM_DOMAIN = "cdn.example.com"

        from apps.integrations.providers.storage_s3 import S3StorageProvider

        with patch("boto3.client") as mock_boto:
            provider = S3StorageProvider()
            mock_boto.return_value.upload_fileobj = MagicMock()

            result = await provider.upload_bytes(
                b"image-data", "test/img.jpg", "image/jpeg"
            )

        assert result.url == "https://cdn.example.com/test/img.jpg"
        assert result.key == "test/img.jpg"
        assert result.size_bytes == 10

    @pytest.mark.asyncio
    async def test_get_public_url_custom_domain(self, settings):
        settings.AWS_S3_ENDPOINT_URL = "https://s3.example.com"
        settings.AWS_ACCESS_KEY_ID = "test-key"
        settings.AWS_SECRET_ACCESS_KEY = "test-secret"
        settings.AWS_STORAGE_BUCKET_NAME = "test-bucket"
        settings.AWS_S3_CUSTOM_DOMAIN = "cdn.example.com"
        settings.PUBLIC_MEDIA_BASE_URL = ""

        from apps.integrations.providers.storage_s3 import S3StorageProvider

        with patch("boto3.client"):
            provider = S3StorageProvider()
            url = await provider.get_public_url("my/file.jpg")

        assert url == "https://cdn.example.com/my/file.jpg"

    @pytest.mark.asyncio
    async def test_get_public_url_no_custom_domain(self, settings):
        settings.AWS_S3_ENDPOINT_URL = "https://s3.example.com"
        settings.AWS_ACCESS_KEY_ID = "test-key"
        settings.AWS_SECRET_ACCESS_KEY = "test-secret"
        settings.AWS_STORAGE_BUCKET_NAME = "test-bucket"
        settings.AWS_S3_CUSTOM_DOMAIN = ""
        settings.PUBLIC_MEDIA_BASE_URL = ""

        from apps.integrations.providers.storage_s3 import S3StorageProvider

        with patch("boto3.client"):
            provider = S3StorageProvider()
            url = await provider.get_public_url("my/file.jpg")

        assert url == "https://s3.example.com/test-bucket/my/file.jpg"

    @pytest.mark.asyncio
    async def test_get_public_url_public_media_base_url(self, settings):
        settings.AWS_S3_ENDPOINT_URL = "https://s3.example.com"
        settings.AWS_ACCESS_KEY_ID = "test-key"
        settings.AWS_SECRET_ACCESS_KEY = "test-secret"
        settings.AWS_STORAGE_BUCKET_NAME = "test-bucket"
        settings.AWS_S3_CUSTOM_DOMAIN = ""
        settings.PUBLIC_MEDIA_BASE_URL = "https://public.example.com"

        from apps.integrations.providers.storage_s3 import S3StorageProvider

        with patch("boto3.client"):
            provider = S3StorageProvider()
            url = await provider.get_public_url("my/file.jpg")

        assert url == "https://public.example.com/assets/media/my/file.jpg"


# ── Registry ─────────────────────────────────────────────────


class TestRegistry:
    def test_get_text_provider_openai(self, settings):
        settings.OPENAI_API_KEY = "sk-test"
        settings.TEXT_PROVIDER = "openai"

        from apps.integrations.registry import get_text_provider
        get_text_provider.cache_clear()

        provider = get_text_provider()
        from apps.integrations.providers.openai_text import OpenAITextProvider
        assert isinstance(provider, OpenAITextProvider)
        get_text_provider.cache_clear()

    def test_get_text_provider_unknown_raises(self, settings):
        settings.TEXT_PROVIDER = "anthropic"

        from apps.integrations.registry import get_text_provider
        get_text_provider.cache_clear()

        with pytest.raises(ValueError, match="desconocido"):
            get_text_provider()
        get_text_provider.cache_clear()

    def test_get_image_provider_openai(self, settings):
        settings.OPENAI_API_KEY = "sk-test"
        settings.IMAGE_PROVIDER = "openai"

        from apps.integrations.registry import get_image_provider
        get_image_provider.cache_clear()

        provider = get_image_provider()
        from apps.integrations.providers.openai_images import OpenAIImageProvider
        assert isinstance(provider, OpenAIImageProvider)
        get_image_provider.cache_clear()

    def test_get_video_provider_not_implemented(self, settings):
        settings.VIDEO_PROVIDER = "creatomate"

        from apps.integrations.registry import get_video_provider
        get_video_provider.cache_clear()

        with pytest.raises(NotImplementedError):
            get_video_provider()
        get_video_provider.cache_clear()
