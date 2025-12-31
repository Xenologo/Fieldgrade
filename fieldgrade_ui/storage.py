from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol


class BlobStore(Protocol):
    def put_bytes(self, key: str, data: bytes, *, content_type: Optional[str] = None) -> str:
        """Store bytes under a key and return a stable URI (e.g. s3://... or file://...)."""

        ...

    def exists(self, key: str) -> bool:
        """Return True if key exists."""

        ...


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class StoredBlob:
    key: str
    uri: str
    sha256: str


class LocalDirBlobStore:
    """A minimal local blob store rooted at a directory.

    This is primarily a dev/test implementation and a shape-compatible stand-in
    for S3. It never mutates the source file; it only writes a new object.
    """

    def __init__(self, root: Path):
        self.root = Path(root)

    def _path_for_key(self, key: str) -> Path:
        safe_key = key.lstrip("/")
        p = (self.root / safe_key).resolve()
        # best-effort safety: ensure key doesn't escape root
        if self.root.resolve() not in p.parents and p != self.root.resolve():
            raise ValueError(f"invalid_key_escape: {key}")
        return p

    def put_bytes(self, key: str, data: bytes, *, content_type: Optional[str] = None) -> str:
        p = self._path_for_key(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return f"file://{p.as_posix()}"

    def exists(self, key: str) -> bool:
        return self._path_for_key(key).exists()


class S3BlobStore:
    """S3-compatible blob store.

    Requires `boto3` to be installed in the environment/image.
    """

    def __init__(self, *, bucket: str, prefix: str = ""):
        self.bucket = bucket
        self.prefix = (prefix or "").lstrip("/")

        try:
            import boto3  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "S3BlobStore requires boto3. Install it in the image or set FG_BUNDLE_STORE=local."
            ) from e

        self._s3 = boto3.client("s3")

    def _key(self, key: str) -> str:
        k = key.lstrip("/")
        return f"{self.prefix}{k}" if self.prefix else k

    def put_bytes(self, key: str, data: bytes, *, content_type: Optional[str] = None) -> str:
        k = self._key(key)
        extra = {}
        if content_type:
            extra["ContentType"] = content_type
        self._s3.put_object(Bucket=self.bucket, Key=k, Body=data, **extra)
        return f"s3://{self.bucket}/{k}"

    def exists(self, key: str) -> bool:
        k = self._key(key)
        try:
            self._s3.head_object(Bucket=self.bucket, Key=k)
            return True
        except Exception:
            return False


def bundle_store_backend() -> str:
    return (os.environ.get("FG_BUNDLE_STORE") or "local").strip().lower()


def _default_local_store_root(repo_root: Path) -> Path:
    return repo_root / "fieldgrade_ui" / "runtime" / "object_store"


def get_blob_store(repo_root: Path) -> BlobStore:
    backend = bundle_store_backend()
    if backend in ("local", "filesystem", "fs"):
        root = Path(os.environ.get("FG_OBJECT_STORE_ROOT") or _default_local_store_root(repo_root))
        return LocalDirBlobStore(root)

    if backend in ("s3", "minio"):
        bucket = (os.environ.get("FG_S3_BUCKET") or "").strip()
        if not bucket:
            raise RuntimeError("missing FG_S3_BUCKET for FG_BUNDLE_STORE=s3")
        prefix = (os.environ.get("FG_S3_PREFIX") or "").strip()
        return S3BlobStore(bucket=bucket, prefix=prefix)

    raise RuntimeError(f"unknown FG_BUNDLE_STORE={backend!r}")


def publish_bundle_if_configured(repo_root: Path, bundle_path: Path) -> Optional[StoredBlob]:
    """Optionally publish a sealed bundle to object storage.

    Default behavior is a no-op (`FG_BUNDLE_STORE=local`). When enabled, the
    bundle is uploaded under a hash-addressed key to preserve immutability.
    """

    backend = bundle_store_backend()
    if backend in ("local", "filesystem", "fs"):
        return None

    data = bundle_path.read_bytes()
    sha = _sha256_bytes(data)
    key = f"bundles/{sha}.zip"

    store = get_blob_store(repo_root)
    uri = store.put_bytes(key, data, content_type="application/zip")
    if not store.exists(key):
        raise RuntimeError("bundle_store_write_failed")

    return StoredBlob(key=key, uri=uri, sha256=sha)
