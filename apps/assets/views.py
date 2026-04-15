from __future__ import annotations

import re

from botocore.exceptions import ClientError
from django.conf import settings
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_safe

from apps.integrations.providers.storage_s3 import get_s3_client


_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


@require_safe
def serve_asset(request, key: str):
    if not settings.USE_S3:
        raise Http404("Storage backend no disponible")

    normalized_key = key.lstrip("/")
    range_header = request.headers.get("Range", "")
    s3_params = {
        "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
        "Key": normalized_key,
    }
    if range_header:
        if not _RANGE_RE.fullmatch(range_header):
            return HttpResponse(status=416)
        s3_params["Range"] = range_header

    try:
        response = get_s3_client().get_object(**s3_params)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"NoSuchKey", "404"}:
            raise Http404("Asset no encontrado") from exc
        if error_code in {"InvalidRange", "416"}:
            return HttpResponse(status=416)
        raise

    body = response["Body"]
    stream = StreamingHttpResponse(
        body.iter_chunks(),
        content_type=response.get("ContentType") or "application/octet-stream",
        status=206 if range_header else 200,
    )
    if response.get("ContentLength") is not None:
        stream["Content-Length"] = str(response["ContentLength"])
    if response.get("ETag"):
        stream["ETag"] = response["ETag"]
    if response.get("ContentRange"):
        stream["Content-Range"] = response["ContentRange"]
    stream["Accept-Ranges"] = "bytes"
    stream["Cache-Control"] = "public, max-age=3600"
    stream["Content-Disposition"] = "inline"
    return stream