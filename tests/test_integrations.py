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
)
from apps.integrations.routing import resolve_generation_config


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
        assert req.model == ""


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

    @pytest.mark.asyncio
    async def test_gpt5_uses_max_completion_tokens(self):
        from apps.integrations.providers.openai_text import OpenAITextProvider

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ok"
        mock_response.model = "gpt-5.4-mini"
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)
        mock_response.model_dump.return_value = {}

        provider = OpenAITextProvider(api_key="sk-test")

        with patch.object(
            provider._client.chat.completions, "create",
            new_callable=AsyncMock, return_value=mock_response,
        ) as mock_create:
            await provider.generate(
                TextGenerationRequest(
                    system_prompt="sys",
                    user_prompt="user",
                    model="gpt-5.4-mini",
                    max_tokens=1234,
                )
            )

        call_kwargs = mock_create.call_args[1]
        assert call_kwargs["max_completion_tokens"] == 1234
        assert "max_tokens" not in call_kwargs


class TestGeminiTextProvider:
    @pytest.mark.asyncio
    async def test_generate_uses_structured_output_when_requested(self):
        from apps.integrations.providers.gemini_text import GeminiTextProvider

        mock_response = MagicMock()
        mock_response.text = '{"result": "ok"}'
        mock_response.model_version = "gemini-2.5-flash"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10,
            candidates_token_count=5,
            thoughts_token_count=2,
        )
        mock_response.model_dump.return_value = {}

        provider = GeminiTextProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.gemini_text.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_to_thread:
            result = await provider.generate(
                TextGenerationRequest(
                    system_prompt="sys",
                    user_prompt="user",
                    model="gemini-2.5-flash",
                    response_format="json_object",
                )
            )

        assert result.text == '{"result": "ok"}'
        assert result.model == "gemini-2.5-flash"
        assert result.completion_tokens == 7
        assert result.cost_usd == pytest.approx(0.0000205)
        assert mock_to_thread.call_args.kwargs["config"].response_mime_type == "application/json"

    @pytest.mark.asyncio
    async def test_generate_uses_official_flash_lite_rates(self):
        from apps.integrations.providers.gemini_text import GeminiTextProvider

        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_response.model_version = "gemini-2.5-flash-lite"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=1000,
            candidates_token_count=500,
            thoughts_token_count=250,
        )
        mock_response.model_dump.return_value = {}

        provider = GeminiTextProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.gemini_text.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.generate(
                TextGenerationRequest(
                    system_prompt="sys",
                    user_prompt="user",
                    model="gemini-2.5-flash-lite",
                )
            )

        assert result.cost_usd == pytest.approx(0.0004)
        assert result.completion_tokens == 750

    @pytest.mark.asyncio
    async def test_generate_uses_long_context_pro_rates(self):
        from apps.integrations.providers.gemini_text import GeminiTextProvider

        mock_response = MagicMock()
        mock_response.text = "ok"
        mock_response.model_version = "gemini-2.5-pro"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=250000,
            candidates_token_count=10,
            thoughts_token_count=0,
        )
        mock_response.model_dump.return_value = {}

        provider = GeminiTextProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.gemini_text.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.generate(
                TextGenerationRequest(
                    system_prompt="sys",
                    user_prompt="user",
                    model="gemini-2.5-pro",
                )
            )

        assert result.cost_usd == pytest.approx(0.62515)


# ── OpenAI Image Provider ────────────────────────────────────


class TestOpenAIImageProvider:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("model", "expected_cost"),
        [
            ("gpt-image-1.5", 0.050),
            ("gpt-image-1", 0.063),
            ("gpt-image-1-mini", 0.015),
        ],
    )
    async def test_generate_uses_official_medium_quality_pricing(self, model, expected_cost):
        from apps.integrations.providers.openai_images import OpenAIImageProvider

        mock_img = MagicMock()
        mock_img.url = "https://oaidalleapiprodscus.blob.core.windows.net/img.jpg"

        mock_response = MagicMock()
        mock_response.data = [mock_img]

        provider = OpenAIImageProvider(api_key="sk-test")

        with patch.object(
            provider._client.images, "generate",
            new_callable=AsyncMock, return_value=mock_response,
        ) as mock_generate:
            result = await provider.generate(
                ImageGenerationRequest(prompt="a sunset", model=model)
            )

        assert result.cost_usd == pytest.approx(expected_cost)
        assert result.width == 1024
        assert result.height == 1536
        assert mock_generate.call_args.kwargs["quality"] == "medium"

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
        assert result.cost_usd == pytest.approx(0.063)
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
        assert result.cost_usd == pytest.approx(0.063)
        assert result.content_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_generate_uses_actual_returned_image_count_for_cost(self):
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
                ImageGenerationRequest(prompt="a sunset", num_images=3)
            )

        assert result.cost_usd == pytest.approx(0.063)

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
        assert mock_generate.call_args.kwargs["quality"] == "medium"


class TestGeminiImageProvider:
    @pytest.mark.asyncio
    async def test_generate_returns_inline_images(self):
        from apps.integrations.providers.gemini_images import GeminiImageProvider

        part = MagicMock()
        part.thought = False
        part.inline_data = MagicMock(
            data=base64.b64encode(b"image-bytes").decode("ascii"),
            mime_type="image/jpeg",
        )
        candidate = MagicMock()
        candidate.content = MagicMock(parts=[part])
        mock_response = MagicMock()
        mock_response.candidates = [candidate]
        mock_response.model_version = "gemini-3-pro-image-preview"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=100,
            candidates_token_count=20,
            thoughts_token_count=5,
        )
        mock_response.model_dump.return_value = {}

        provider = GeminiImageProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.gemini_images.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_to_thread:
            result = await provider.generate(
                ImageGenerationRequest(
                    prompt="hero product shot",
                    model="gemini-3-pro-image-preview",
                    width=1080,
                    height=1350,
                )
            )

        assert result.image_urls == []
        assert result.image_bytes == [b"image-bytes"]
        assert result.content_type == "image/jpeg"
        assert result.cost_usd == pytest.approx(0.1345)
        config = mock_to_thread.call_args.kwargs["config"]
        assert config.response_modalities == ["IMAGE"]
        assert config.image_config.aspect_ratio is not None
        assert config.image_config.image_size == "2K"

    @pytest.mark.asyncio
    async def test_generate_ignores_thought_images_for_assets_and_cost(self):
        from apps.integrations.providers.gemini_images import GeminiImageProvider

        thought_part = MagicMock()
        thought_part.thought = True
        thought_part.inline_data = MagicMock(
            data=base64.b64encode(b"draft-image").decode("ascii"),
            mime_type="image/jpeg",
        )

        final_part = MagicMock()
        final_part.thought = False
        final_part.inline_data = MagicMock(
            data=base64.b64encode(b"final-image").decode("ascii"),
            mime_type="image/jpeg",
        )

        candidate = MagicMock()
        candidate.content = MagicMock(parts=[thought_part, final_part])

        mock_response = MagicMock()
        mock_response.candidates = [candidate]
        mock_response.model_version = "gemini-3.1-flash-image-preview"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=0,
            candidates_token_count=0,
            thoughts_token_count=0,
        )
        mock_response.model_dump.return_value = {}

        provider = GeminiImageProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.gemini_images.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.generate(
                ImageGenerationRequest(
                    prompt="hero product shot",
                    model="gemini-3.1-flash-image-preview",
                    width=512,
                    height=512,
                )
            )

        assert result.image_bytes == [b"final-image"]
        assert result.cost_usd == pytest.approx(0.045)

    @pytest.mark.asyncio
    async def test_generate_uses_fixed_1k_pricing_for_gemini_25_flash_image(self):
        from apps.integrations.providers.gemini_images import GeminiImageProvider

        part = MagicMock()
        part.thought = False
        part.inline_data = MagicMock(
            data=base64.b64encode(b"image-bytes").decode("ascii"),
            mime_type="image/jpeg",
        )
        candidate = MagicMock()
        candidate.content = MagicMock(parts=[part])
        mock_response = MagicMock()
        mock_response.candidates = [candidate]
        mock_response.model_version = "gemini-2.5-flash-image"
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=0,
            candidates_token_count=0,
            thoughts_token_count=0,
        )
        mock_response.model_dump.return_value = {}

        provider = GeminiImageProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.gemini_images.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_to_thread:
            result = await provider.generate(
                ImageGenerationRequest(
                    prompt="hero product shot",
                    model="gemini-2.5-flash-image",
                    width=4096,
                    height=4096,
                )
            )

        assert result.cost_usd == pytest.approx(0.039)
        config = mock_to_thread.call_args.kwargs["config"]
        assert getattr(config.image_config, "image_size", None) is None


class TestImagen4ImageProvider:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("model", "expected_cost"),
        [
            ("imagen-4.0-fast-generate-001", 0.020),
            ("imagen-4.0-generate-001", 0.040),
            ("imagen-4.0-ultra-generate-001", 0.060),
        ],
    )
    async def test_generate_uses_flat_official_pricing(self, model, expected_cost):
        from apps.integrations.providers.imagen4 import Imagen4ImageProvider

        generated = MagicMock()
        generated.image = MagicMock(image_bytes=b"image-bytes")
        mock_response = MagicMock()
        mock_response.generated_images = [generated]

        provider = Imagen4ImageProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.imagen4.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.generate(
                ImageGenerationRequest(
                    prompt="catalog shot",
                    model=model,
                    width=4096,
                    height=4096,
                )
            )

        assert result.image_bytes == [b"image-bytes"]
        assert result.cost_usd == pytest.approx(expected_cost)


class TestCreatomateVideoProvider:
    @pytest.mark.asyncio
    async def test_generate_polls_until_render_ready(self, settings):
        import httpx

        settings.CREATOMATE_API_KEY = "ct-test"
        from apps.integrations.providers.creatomate_video import CreatomateVideoProvider

        provider = CreatomateVideoProvider(api_key="ct-test")

        create_resp = httpx.Response(
            200,
            json={"id": "render_1", "status": "planned"},
            request=httpx.Request("POST", "https://api.creatomate.com/v2/renders"),
        )
        poll_resp = httpx.Response(
            200,
            json={
                "id": "render_1",
                "status": "succeeded",
                "url": "https://cdn.creatomate.com/render.mp4",
                "snapshot_url": "https://cdn.creatomate.com/render.jpg",
                "duration": 8,
            },
            request=httpx.Request("GET", "https://api.creatomate.com/v2/renders/render_1"),
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=create_resp), patch(
            "httpx.AsyncClient.get", new_callable=AsyncMock, return_value=poll_resp,
        ), patch("apps.integrations.providers.creatomate_video.asyncio.sleep", new_callable=AsyncMock):
            result = await provider.generate(
                VideoGenerationRequest(
                    render_spec={"output_format": "mp4", "width": 1080, "height": 1920, "elements": []},
                    model="creatomate-renderscript",
                )
            )

        assert result.video_url == "https://cdn.creatomate.com/render.mp4"
        assert result.thumbnail_url == "https://cdn.creatomate.com/render.jpg"
        assert result.duration_seconds == 8

    @pytest.mark.asyncio
    async def test_generate_requires_payload(self, settings):
        settings.CREATOMATE_API_KEY = "ct-test"
        from apps.integrations.providers.creatomate_video import CreatomateVideoProvider

        provider = CreatomateVideoProvider(api_key="ct-test")

        with pytest.raises(ValueError, match="template_id o render_spec"):
            await provider.generate(VideoGenerationRequest(model="creatomate-renderscript"))


class TestVeoVideoProvider:
    @pytest.mark.asyncio
    async def test_generate_downloads_video_bytes(self, settings):
        settings.GEMINI_API_KEY = "gm-test"
        settings.VEO_VIDEO_MODEL = "veo-3.1-generate-preview"

        from apps.integrations.providers.veo_video import VeoVideoProvider

        provider = VeoVideoProvider(api_key="gm-test")
        pending_operation = MagicMock(done=False)
        completed_operation = MagicMock(done=True)
        completed_operation.response = MagicMock(
            generated_videos=[MagicMock(video=MagicMock(uri="gs://video", mime_type="video/mp4"))]
        )

        with patch(
            "apps.integrations.providers.veo_video.asyncio.to_thread",
            new_callable=AsyncMock,
            side_effect=[pending_operation, completed_operation, b"video-bytes"],
        ) as mock_to_thread, patch("apps.integrations.providers.veo_video.asyncio.sleep", new_callable=AsyncMock):
            result = await provider.generate(
                VideoGenerationRequest(
                    prompt="Vertical cinematic video",
                    negative_prompt="blurry, watermark, distorted anatomy",
                    model="veo-3.1-generate-preview",
                    duration_seconds=7,
                    width=1080,
                    height=1920,
                )
            )

        generate_call_kwargs = mock_to_thread.call_args_list[0].kwargs
        generate_config = generate_call_kwargs["config"]
        dumped_config = generate_config.model_dump(exclude_none=True)
        assert "generate_audio" not in dumped_config
        assert "enhance_prompt" not in dumped_config
        assert "negative_prompt" not in dumped_config
        assert generate_call_kwargs["prompt"] == "Vertical cinematic video\n\nAvoid: blurry, watermark, distorted anatomy"

        assert result.video_bytes == b"video-bytes"
        assert result.model == "veo-3.1-generate-preview"
        assert result.duration_seconds == 8
        assert result.content_type == "video/mp4"


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

    def test_get_text_provider_gemini(self, settings):
        settings.GEMINI_API_KEY = "gm-test"

        from apps.integrations.registry import get_text_provider
        get_text_provider.cache_clear()

        provider = get_text_provider("gemini")
        from apps.integrations.providers.gemini_text import GeminiTextProvider
        assert isinstance(provider, GeminiTextProvider)
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

    def test_get_image_provider_gemini(self, settings):
        settings.GEMINI_API_KEY = "gm-test"

        from apps.integrations.registry import get_image_provider
        get_image_provider.cache_clear()

        provider = get_image_provider("gemini")
        from apps.integrations.providers.gemini_images import GeminiImageProvider
        assert isinstance(provider, GeminiImageProvider)
        get_image_provider.cache_clear()

    def test_get_video_provider_creatomate(self, settings):
        settings.VIDEO_PROVIDER = "creatomate"
        settings.CREATOMATE_API_KEY = "ct-test"

        from apps.integrations.registry import get_video_provider
        get_video_provider.cache_clear()

        provider = get_video_provider()
        from apps.integrations.providers.creatomate_video import CreatomateVideoProvider
        assert isinstance(provider, CreatomateVideoProvider)
        get_video_provider.cache_clear()

    def test_get_video_provider_veo(self, settings):
        settings.GEMINI_API_KEY = "gm-test"

        from apps.integrations.registry import get_video_provider
        get_video_provider.cache_clear()

        provider = get_video_provider("veo")
        from apps.integrations.providers.veo_video import VeoVideoProvider
        assert isinstance(provider, VeoVideoProvider)
        get_video_provider.cache_clear()


class TestRoutingResolution:
    def test_resolve_uses_settings_defaults(self, settings):
        settings.TEXT_PROVIDER = "gemini"
        settings.GEMINI_TEXT_MODEL = "gemini-2.5-flash"

        resolved = resolve_generation_config(capability="text", agent_type="copy")

        assert resolved.provider == "gemini"
        assert resolved.model == "gemini-2.5-flash"

    def test_resolve_prefers_brand_agent_override(self, settings):
        settings.TEXT_PROVIDER = "openai"
        settings.OPENAI_REASONING_MODEL = "gpt-4o"

        resolved = resolve_generation_config(
            capability="text",
            agent_type="carousel",
            brand_defaults={
                "text": {
                    "carousel": {"provider": "gemini", "model": "gemini-2.5-pro"}
                }
            },
        )

        assert resolved.provider == "gemini"
        assert resolved.model == "gemini-2.5-pro"
        assert resolved.provider_source == "brand.text.carousel.provider"

    def test_resolve_prefers_brief_override_over_brand(self, settings):
        settings.IMAGE_PROVIDER = "openai"
        settings.OPENAI_IMAGE_MODEL = "gpt-image-1"

        resolved = resolve_generation_config(
            capability="image",
            agent_type="image",
            brand_defaults={
                "image": {
                    "default": {"provider": "openai", "model": "gpt-image-1"}
                }
            },
            brief_overrides={
                "image": {
                    "default": {
                        "provider": "gemini",
                        "model": "gemini-3-pro-image-preview",
                    }
                }
            },
        )

        assert resolved.provider == "gemini"
        assert resolved.model == "gemini-3-pro-image-preview"
        assert resolved.provider_source == "brief.image.default.provider"

    def test_resolve_imagen_provider(self, settings):
        settings.IMAGE_PROVIDER = "openai"

        resolved = resolve_generation_config(
            capability="image",
            agent_type="image",
            brief_overrides={
                "image": {
                    "default": {
                        "provider": "imagen",
                        "model": "imagen-4.0-generate-001",
                    }
                }
            },
        )

        assert resolved.provider == "imagen"
        assert resolved.model == "imagen-4.0-generate-001"

    def test_resolve_imagen_default_model(self, settings):
        settings.IMAGE_PROVIDER = "imagen"
        settings.IMAGEN_MODEL = "imagen-4.0-fast-generate-001"

        resolved = resolve_generation_config(capability="image", agent_type="image")

        assert resolved.provider == "imagen"
        assert resolved.model == "imagen-4.0-fast-generate-001"

    def test_resolve_complex_agent_uses_reasoning_model(self, settings):
        settings.TEXT_PROVIDER = "openai"
        settings.OPENAI_REASONING_MODEL = "gpt-5.4"

        resolved = resolve_generation_config(capability="text", agent_type="carousel")

        assert resolved.model == "gpt-5.4"

    def test_resolve_simple_agent_uses_text_model(self, settings):
        settings.TEXT_PROVIDER = "openai"
        settings.OPENAI_TEXT_MODEL = "gpt-5.4-mini"

        resolved = resolve_generation_config(capability="text", agent_type="copy")

        assert resolved.model == "gpt-5.4-mini"

    def test_resolve_video_defaults(self, settings):
        settings.VIDEO_PROVIDER = "veo"
        settings.VEO_VIDEO_MODEL = "veo-3.1-fast-generate-preview"

        resolved = resolve_generation_config(capability="video", agent_type="video")

        assert resolved.provider == "veo"
        assert resolved.model == "veo-3.1-fast-generate-preview"

    def test_resolve_video_brief_override(self, settings):
        settings.VIDEO_PROVIDER = "creatomate"
        settings.CREATOMATE_VIDEO_MODEL = "creatomate-renderscript"

        resolved = resolve_generation_config(
            capability="video",
            agent_type="video",
            brief_overrides={
                "video": {
                    "default": {
                        "provider": "veo",
                        "model": "veo-3.1-generate-preview",
                    }
                }
            },
        )

        assert resolved.provider == "veo"
        assert resolved.model == "veo-3.1-generate-preview"


# ── Model Catalog ────────────────────────────────────────────


class TestModelCatalog:
    def test_get_models_for_openai_text(self):
        from apps.integrations.model_catalog import get_models_for

        models = get_models_for("openai", "text")
        values = [m.value for m in models]
        assert "gpt-5.4" in values
        assert "gpt-5.4-mini" in values
        assert "gpt-5.4-nano" in values
        assert "gpt-4o" in values
        assert "gpt-4o-mini" in values
        assert len(models) >= 7

    def test_get_models_for_gemini_text(self):
        from apps.integrations.model_catalog import get_models_for

        models = get_models_for("gemini", "text")
        values = [m.value for m in models]
        assert "gemini-2.5-flash" in values
        assert "gemini-2.5-pro" in values
        assert len(models) >= 5

    def test_get_models_for_openai_image(self):
        from apps.integrations.model_catalog import get_models_for

        models = get_models_for("openai", "image")
        values = [m.value for m in models]
        assert "gpt-image-1" in values
        assert "gpt-image-1.5" in values
        assert "gpt-image-1-mini" in values
        assert "dall-e-3" in values

    def test_get_models_for_video(self):
        from apps.integrations.model_catalog import get_models_for

        models = get_models_for("veo", "video")
        values = [m.value for m in models]
        assert "veo-3.1-generate-preview" in values
        assert "veo-3.1-fast-generate-preview" in values

    def test_get_models_for_imagen(self):
        from apps.integrations.model_catalog import get_models_for

        models = get_models_for("imagen", "image")
        values = [m.value for m in models]
        assert "imagen-4.0-generate-001" in values
        assert "imagen-4.0-ultra-generate-001" in values
        assert "imagen-4.0-fast-generate-001" in values
        assert len(models) == 3

    def test_get_models_for_unknown_returns_empty(self):
        from apps.integrations.model_catalog import get_models_for

        assert get_models_for("anthropic", "text") == []

    def test_get_providers_for_text(self):
        from apps.integrations.model_catalog import get_providers_for

        providers = get_providers_for("text")
        assert "openai" in providers
        assert "gemini" in providers
        assert "imagen" not in providers

    def test_get_providers_for_image(self):
        from apps.integrations.model_catalog import get_providers_for

        providers = get_providers_for("image")
        assert "openai" in providers
        assert "gemini" in providers
        assert "imagen" in providers

    def test_get_providers_for_video(self):
        from apps.integrations.model_catalog import get_providers_for

        providers = get_providers_for("video")
        assert "creatomate" in providers
        assert "veo" in providers

    def test_get_catalog_as_choices(self):
        from apps.integrations.model_catalog import get_catalog_as_choices

        choices = get_catalog_as_choices("openai", "text")
        values = [v for v, _ in choices]
        assert "gpt-5.4" in values
        assert "gpt-5.4-mini" in values
        # Sorted by tier: Potente first
        labels = [lbl for _, lbl in choices]
        assert "Potente" in labels[0]

    def test_get_catalog_as_choices_recommended_star(self):
        from apps.integrations.model_catalog import get_catalog_as_choices

        choices = get_catalog_as_choices("openai", "text")
        recommended = [lbl for v, lbl in choices if v == "gpt-5.4-mini"]
        assert any("★" in lbl for lbl in recommended)

    def test_is_catalog_model_true(self):
        from apps.integrations.model_catalog import is_catalog_model

        assert is_catalog_model("gpt-5.4-mini", "openai", "text") is True
        assert is_catalog_model("imagen-4.0-generate-001", "imagen", "image") is True

    def test_is_catalog_model_false(self):
        from apps.integrations.model_catalog import is_catalog_model

        assert is_catalog_model("gpt-99", "openai", "text") is False
        assert is_catalog_model("gpt-5.4-mini", "gemini", "text") is False

    def test_get_catalog_as_grouped_dict(self):
        from apps.integrations.model_catalog import get_catalog_as_grouped_dict

        data = get_catalog_as_grouped_dict()
        assert "openai" in data
        assert "gemini" in data
        assert "imagen" in data
        assert "veo" in data
        assert "text" in data["openai"]
        assert "image" in data["openai"]
        assert "image" in data["imagen"]
        assert isinstance(data["openai"]["text"], list)
        assert len(data["openai"]["text"]) >= 7

    def test_get_catalog_json_parses(self):
        import json
        from apps.integrations.model_catalog import get_catalog_json

        raw = get_catalog_json()
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)
        assert "openai" in parsed

    def test_each_model_has_required_fields(self):
        from apps.integrations.model_catalog import _CATALOG

        for m in _CATALOG:
            assert m.provider, f"Model {m.value} missing provider"
            assert m.capability in ("text", "image", "video"), f"Model {m.value} bad capability"
            assert m.value, f"Model {m.value} missing value"
            assert m.label, f"Model {m.value} missing label"
            assert m.tier in ("Potente", "Balanceado", "Eficiente"), f"Model {m.value} bad tier"

    def test_every_tier_has_at_least_one_model_per_capability(self):
        from apps.integrations.model_catalog import _CATALOG

        for cap in ("text", "image", "video"):
            tiers = {m.tier for m in _CATALOG if m.capability == cap}
            assert "Potente" in tiers
            assert "Balanceado" in tiers
            assert "Eficiente" in tiers


# ── Imagen 4 Provider ────────────────────────────────────────


class TestImagen4ImageProviderCompatibility:
    @pytest.mark.asyncio
    async def test_generate_returns_image_bytes(self):
        from apps.integrations.providers.imagen4 import Imagen4ImageProvider

        gen_image = MagicMock()
        gen_image.image = MagicMock(image_bytes=b"png-image-data")

        mock_response = MagicMock()
        mock_response.generated_images = [gen_image]

        provider = Imagen4ImageProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.imagen4.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_to_thread:
            result = await provider.generate(
                ImageGenerationRequest(
                    prompt="a sunset over mountains",
                    model="imagen-4.0-generate-001",
                    width=1024,
                    height=1024,
                )
            )

        assert result.image_bytes == [b"png-image-data"]
        assert result.image_urls == []
        assert result.content_type == "image/png"
        assert result.model == "imagen-4.0-generate-001"
        assert result.cost_usd > 0

        call_kwargs = mock_to_thread.call_args.kwargs
        assert call_kwargs["model"] == "imagen-4.0-generate-001"
        assert call_kwargs["prompt"] == "a sunset over mountains"

    @pytest.mark.asyncio
    async def test_generate_handles_memoryview(self):
        from apps.integrations.providers.imagen4 import Imagen4ImageProvider

        gen_image = MagicMock()
        gen_image.image = MagicMock(image_bytes=memoryview(b"mv-image"))

        mock_response = MagicMock()
        mock_response.generated_images = [gen_image]

        provider = Imagen4ImageProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.imagen4.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.generate(
                ImageGenerationRequest(prompt="test", model="imagen-4.0-fast-generate-001")
            )

        assert result.image_bytes == [b"mv-image"]

    @pytest.mark.asyncio
    async def test_generate_empty_response(self):
        from apps.integrations.providers.imagen4 import Imagen4ImageProvider

        mock_response = MagicMock()
        mock_response.generated_images = []

        provider = Imagen4ImageProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.imagen4.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.generate(
                ImageGenerationRequest(prompt="test")
            )

        assert result.image_bytes == []
        assert result.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_generate_multiple_images(self):
        from apps.integrations.providers.imagen4 import Imagen4ImageProvider

        imgs = []
        for i in range(3):
            g = MagicMock()
            g.image = MagicMock(image_bytes=f"img-{i}".encode())
            imgs.append(g)

        mock_response = MagicMock()
        mock_response.generated_images = imgs

        provider = Imagen4ImageProvider(api_key="gm-test")

        with patch(
            "apps.integrations.providers.imagen4.asyncio.to_thread",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await provider.generate(
                ImageGenerationRequest(prompt="test", num_images=3)
            )

        assert len(result.image_bytes) == 3
        assert result.cost_usd == pytest.approx(0.12)

    def test_resolve_aspect_ratio_portrait(self):
        from apps.integrations.providers.imagen4 import _resolve_aspect_ratio

        # 1080/1350 = 0.8, closest to 3:4 (0.75)
        assert _resolve_aspect_ratio(1080, 1350) == "3:4"
        assert _resolve_aspect_ratio(1080, 1920) == "9:16"

    def test_resolve_aspect_ratio_landscape(self):
        from apps.integrations.providers.imagen4 import _resolve_aspect_ratio

        assert _resolve_aspect_ratio(1920, 1080) == "16:9"

    def test_resolve_aspect_ratio_square(self):
        from apps.integrations.providers.imagen4 import _resolve_aspect_ratio

        assert _resolve_aspect_ratio(1080, 1080) == "1:1"

    def test_resolve_image_size(self):
        from apps.integrations.providers.imagen4 import _resolve_image_size

        assert _resolve_image_size(1024, 1024) == "1K"
        assert _resolve_image_size(1080, 1350) == "2K"
        assert _resolve_image_size(512, 512) == "1K"

    def test_calculate_cost(self):
        from apps.integrations.providers.imagen4 import _calculate_cost

        cost = _calculate_cost("imagen-4.0-generate-001", 1)
        assert cost == 0.040

        cost_multi = _calculate_cost("imagen-4.0-generate-001", 2)
        assert cost_multi == 0.080

        assert _calculate_cost("imagen-4.0-generate-001", 0) == 0.0


# ── Registry — Imagen ────────────────────────────────────────


class TestRegistryImagen:
    def test_get_image_provider_imagen(self, settings):
        settings.GEMINI_API_KEY = "gm-test"

        from apps.integrations.registry import get_image_provider
        get_image_provider.cache_clear()

        provider = get_image_provider("imagen")
        from apps.integrations.providers.imagen4 import Imagen4ImageProvider
        assert isinstance(provider, Imagen4ImageProvider)
        get_image_provider.cache_clear()


# ── OpenAI Cost Updates ──────────────────────────────────────


class TestOpenAICostUpdates:
    @pytest.mark.asyncio
    async def test_gpt54_mini_cost(self):
        from apps.integrations.providers.openai_text import OpenAITextProvider

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "output"
        mock_response.model = "gpt-5.4-mini"
        mock_response.usage = MagicMock(prompt_tokens=1000, completion_tokens=500)
        mock_response.model_dump.return_value = {}

        provider = OpenAITextProvider(api_key="sk-test")

        with patch.object(
            provider._client.chat.completions, "create",
            new_callable=AsyncMock, return_value=mock_response,
        ):
            result = await provider.generate(
                TextGenerationRequest(
                    system_prompt="s", user_prompt="u", model="gpt-5.4-mini"
                )
            )

        # gpt-5.4-mini: input=0.75/M, output=4.50/M
        # (1000 * 0.75 + 500 * 4.50) / 1_000_000 = 0.003
        assert abs(result.cost_usd - 0.003) < 0.0001

    @pytest.mark.asyncio
    async def test_gpt_image_15_cost(self):
        from apps.integrations.providers.openai_images import OpenAIImageProvider

        mock_img = MagicMock()
        mock_img.url = "https://example.com/img.jpg"

        mock_response = MagicMock()
        mock_response.data = [mock_img]

        provider = OpenAIImageProvider(api_key="sk-test")

        with patch.object(
            provider._client.images, "generate",
            new_callable=AsyncMock, return_value=mock_response,
        ) as mock_generate:
            result = await provider.generate(
                ImageGenerationRequest(
                    prompt="test", model="gpt-image-1.5",
                    width=1024, height=1024,
                )
            )

        assert result.cost_usd == pytest.approx(0.034)
        assert mock_generate.call_args.kwargs["quality"] == "medium"
