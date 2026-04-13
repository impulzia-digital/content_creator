"""Tests para apps.assets — Asset."""

import pytest

from apps.assets.models import Asset


@pytest.mark.django_db
class TestAsset:
    def test_create_image_asset(self, variant):
        asset = Asset.objects.create(
            variant=variant,
            asset_type=Asset.AssetType.IMAGE,
            source=Asset.Source.GENERATED,
            file_url="https://cdn.example.com/img.jpg",
            file_key="brands/test/content/abc/img.jpg",
            file_size_bytes=150_000,
            mime_type="image/jpeg",
            width=1080,
            height=1350,
            position=0,
            generation_prompt="A clean code infographic",
        )
        assert asset.pk is not None
        assert asset.asset_type == "image"
        assert asset.source == "generated"

    def test_asset_str(self, variant):
        asset = Asset.objects.create(
            variant=variant,
            asset_type=Asset.AssetType.IMAGE,
            file_url="https://cdn.example.com/img.jpg",
            file_key="test.jpg",
            position=2,
        )
        s = str(asset)
        assert "Imagen" in s
        assert "#2" in s

    def test_asset_types(self):
        types = [c[0] for c in Asset.AssetType.choices]
        assert "image" in types
        assert "video" in types
        assert "thumbnail" in types
        assert "audio" in types

    def test_asset_sources(self):
        sources = [c[0] for c in Asset.Source.choices]
        assert "generated" in sources
        assert "uploaded" in sources
        assert "template" in sources

    def test_asset_ordering_by_position(self, variant):
        a2 = Asset.objects.create(
            variant=variant, asset_type=Asset.AssetType.IMAGE,
            file_url="https://x.com/2.jpg", file_key="2.jpg", position=2,
        )
        a0 = Asset.objects.create(
            variant=variant, asset_type=Asset.AssetType.IMAGE,
            file_url="https://x.com/0.jpg", file_key="0.jpg", position=0,
        )
        a1 = Asset.objects.create(
            variant=variant, asset_type=Asset.AssetType.IMAGE,
            file_url="https://x.com/1.jpg", file_key="1.jpg", position=1,
        )
        assets = list(variant.assets.all())
        assert assets[0] == a0
        assert assets[1] == a1
        assert assets[2] == a2

    def test_video_asset_duration(self, variant):
        asset = Asset.objects.create(
            variant=variant,
            asset_type=Asset.AssetType.VIDEO,
            file_url="https://cdn.example.com/reel.mp4",
            file_key="reel.mp4",
            mime_type="video/mp4",
            duration_seconds=30.5,
        )
        assert asset.duration_seconds == 30.5

    def test_asset_defaults(self, variant):
        asset = Asset.objects.create(
            variant=variant,
            asset_type=Asset.AssetType.IMAGE,
            file_url="https://x.com/a.jpg",
            file_key="a.jpg",
        )
        assert asset.source == Asset.Source.GENERATED
        assert asset.file_size_bytes == 0
        assert asset.mime_type == "image/jpeg"
        assert asset.position == 0
        assert asset.generation_prompt == ""
        assert asset.generation_params == {}

    def test_carousel_multiple_assets(self, variant):
        for i in range(7):
            Asset.objects.create(
                variant=variant,
                asset_type=Asset.AssetType.IMAGE,
                file_url=f"https://x.com/slide_{i}.jpg",
                file_key=f"slide_{i}.jpg",
                position=i,
            )
        assert variant.assets.count() == 7
