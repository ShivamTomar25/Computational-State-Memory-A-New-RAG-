from __future__ import annotations

import argparse
import json
from uuid import uuid4

from app.config import settings
from app.storage.dependencies import get_storage_provider
from app.storage.exceptions import StorageProviderError
from app.storage.health import check_storage_readiness
from app.storage.path_builder import validate_object_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Sustha object storage.")
    parser.add_argument(
        "--write",
        action="store_true",
        help="Upload, sign, and delete a synthetic verification object.",
    )
    args = parser.parse_args()

    health = check_storage_readiness()
    print(
        json.dumps(
            {
                "status": health.status,
                "provider": health.provider,
                "bucket": health.bucket,
                "detail": health.detail,
                "can_connect": health.can_connect,
                "bucket_available": health.bucket_available,
            },
            indent=2,
        )
    )

    if not args.write:
        return 0 if health.status in {"healthy", "degraded", "not_configured"} else 1

    if health.status != "healthy":
        return 1

    provider = get_storage_provider()
    object_path = validate_object_path(
        f"{settings.document_storage_environment}/storage-verification/{uuid4()}/probe.txt"
    )

    try:
        provider.upload_bytes(
            object_path=object_path,
            content=b"sustha-storage-verification\n",
            content_type="text/plain",
        )
        exists = provider.object_exists(object_path=object_path)
        signed_download = provider.create_signed_download(object_path=object_path)
        provider.delete_object(object_path=object_path)
    except StorageProviderError as error:
        print(json.dumps({"status": "failed", "detail": str(error)}, indent=2))

        return 1

    print(
        json.dumps(
            {
                "status": "verified",
                "object_exists_after_upload": exists,
                "signed_download_created": bool(signed_download.signed_url),
                "signed_download_expires_in": signed_download.expires_in,
                "cleanup": "attempted",
            },
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
