from __future__ import annotations

from botocore.exceptions import ClientError
from django.conf import settings
from django.http import Http404, StreamingHttpResponse
from django.views.decorators.http import require_safe

from apps.integrations.providers.storage_s3 import get_s3_client


@require_safe
def serve_asset(request, key: str):
    if not settings.USE_S3:
        raise Http404("Storage backend no disponible")

    normalized_key = key.lstrip("/")

    try:
        response = get_s3_client().get_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Key=normalized_key,
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "404"}:
            raise Http404("Asset no encontrado") from exc
        raise

    body = response["Body"]
    stream = StreamingHttpResponse(
        body.iter_chunks(),
        content_type=response.get("ContentType") or "application/octet-stream",
    )
    if response.get("ContentLength") is not None:
        stream["Content-Length"] = str(response["ContentLength"])
    if response.get("ETag"):
        stream["ETag"] = response["ETag"]
    stream["Cache-Control"] = "public, max-age=3600"
    stream["Content-Disposition"] = "inline"
    return stream