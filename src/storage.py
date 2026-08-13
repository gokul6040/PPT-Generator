"""Azure Blob Storage for templates, uploads, and generated PPTs."""
from __future__ import annotations

import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.config import (
    AZURE_STORAGE_CONNECTION_STRING,
    AZURE_STORAGE_CONTAINER,
    AZURE_STORAGE_TEMPLATE_BLOB,
    BLOB_PREFIX_GENERATED,
    BLOB_PREFIX_UPLOADS,
)

PPTX_MIME = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
_TEMP_DIR = Path(tempfile.gettempdir()) / "turnb-ppt-agent"


@dataclass(frozen=True)
class DownloadRef:
    """Reference to a blob-stored PPT file."""

    file_name: str
    blob_name: str


def _require_azure_config() -> None:
    if not AZURE_STORAGE_CONNECTION_STRING.strip():
        raise RuntimeError(
            "AZURE_STORAGE_CONNECTION_STRING is required. "
            "Set it in .env or container environment variables."
        )
    if not AZURE_STORAGE_CONTAINER.strip():
        raise RuntimeError("AZURE_STORAGE_CONTAINER is required.")


def _sanitize_filename(name: str) -> str:
    base = Path(name or "file.pptx").name
    base = re.sub(r"[^\w.\- ]+", "_", base).strip("._ ")
    return base or "file.pptx"


def _container_client():
    from azure.storage.blob import BlobServiceClient

    _require_azure_config()
    client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    return client.get_container_client(AZURE_STORAGE_CONTAINER)


def upload_bytes(blob_name: str, data: bytes, *, content_type: str = PPTX_MIME) -> str:
    from azure.storage.blob import ContentSettings

    blob_name = blob_name.replace("\\", "/").lstrip("/")
    _container_client().upload_blob(
        name=blob_name,
        data=data,
        overwrite=True,
        content_settings=ContentSettings(content_type=content_type),
    )
    return blob_name


def download_bytes(blob_name: str) -> bytes:
    blob_name = blob_name.replace("\\", "/").lstrip("/")
    return _container_client().download_blob(blob_name).readall()


def blob_exists(blob_name: str) -> bool:
    blob_name = blob_name.replace("\\", "/").lstrip("/")
    return bool(_container_client().get_blob_client(blob_name).exists())


def materialize_blob_to_temp(blob_name: str, *, suffix: str = ".pptx") -> str:
    """Download a blob to a temp file for python-pptx (cached per blob name)."""
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)
    safe_key = re.sub(r"[^\w.\-]+", "_", blob_name)
    local_path = _TEMP_DIR / f"{safe_key}{suffix}"
    if local_path.exists() and local_path.stat().st_size > 0:
        return str(local_path)
    local_path.write_bytes(download_bytes(blob_name))
    return str(local_path)


def save_generated_ppt(session_id: str, pptx_bytes: bytes, file_name: str) -> DownloadRef:
    file_name = _sanitize_filename(file_name)
    blob_name = f"{BLOB_PREFIX_GENERATED}/{session_id}/{file_name}"
    upload_bytes(blob_name, pptx_bytes)
    return DownloadRef(file_name=file_name, blob_name=blob_name)


def upload_user_template(session_id: str, file_name: str, data: bytes) -> DownloadRef:
    file_name = _sanitize_filename(file_name)
    blob_name = f"{BLOB_PREFIX_UPLOADS}/{session_id}/{file_name}"
    upload_bytes(blob_name, data)
    return DownloadRef(file_name=file_name, blob_name=blob_name)


def resolve_default_template_path() -> str:
    """Return a temp local path to the default template from blob."""
    return materialize_blob_to_temp(AZURE_STORAGE_TEMPLATE_BLOB)


def resolve_template_path(
    session_id: str,
    *,
    uploaded_name: str | None,
    uploaded_bytes: bytes | None,
    uploaded_blob: str | None,
) -> str:
    """
    Return a temp local path for python-pptx Presentation().
    User-uploaded template takes priority over the default blob template.
    """
    if uploaded_bytes:
        blob_name = uploaded_blob
        if not blob_name:
            ref = upload_user_template(session_id, uploaded_name or "uploaded_template.pptx", uploaded_bytes)
            blob_name = ref.blob_name
        return materialize_blob_to_temp(blob_name)

    return resolve_default_template_path()


def read_download(*, blob_name: str, file_name: str | None = None) -> tuple[bytes, str]:
    """Load PPT bytes from blob for download."""
    name = _sanitize_filename(file_name or "turnb_case_study.pptx")
    return download_bytes(blob_name), name


def download_ref_from_message(msg: dict) -> DownloadRef | None:
    blob_name = msg.get("download_blob")
    file_name = msg.get("download_file_name")
    if not blob_name:
        return None
    return DownloadRef(
        file_name=_sanitize_filename(file_name or "turnb_case_study.pptx"),
        blob_name=blob_name,
    )


def can_serve_download(msg: dict) -> bool:
    ref = download_ref_from_message(msg)
    if not ref:
        return False
    try:
        return blob_exists(ref.blob_name)
    except Exception:
        return False
