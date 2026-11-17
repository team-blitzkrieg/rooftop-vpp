"""Where a trained model file lives. There is no hosted MLflow server.

Supabase Storage is preferred. A GitHub Release asset is the other free option.
If neither is configured, the local directory path is stored and nothing is uploaded.
Local MLflow is not required. A developer can point the MLflow CLI at
forecasting/models on their own machine. This package does not import it.
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def materialize_model(artefact_url: str | None, version: str) -> Path:
    """Return a directory that contains model.txt. Does not upload anything."""
    if artefact_url:
        local = Path(artefact_url)
        if local.is_dir() and (local / "model.txt").is_file():
            return local
        if local.is_file() and local.name == "model.txt":
            return local.parent
    candidate = Path("forecasting/models") / version
    if (candidate / "model.txt").is_file():
        return candidate
    if artefact_url and artefact_url.startswith("http"):
        return _download_zip(artefact_url, version)
    raise RuntimeError(f"No model files for {version}")


def _download_zip(url: str, version: str) -> Path:
    import io
    import tempfile

    headers = {"User-Agent": "rooftop-vpp"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if key and "supabase" in url:
        headers["Authorization"] = f"Bearer {key}"
        headers["apikey"] = key
    request = Request(url, headers=headers, method="GET")
    with urlopen(request, timeout=60) as response:
        payload = response.read()
    dest = Path(tempfile.mkdtemp()) / version
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        archive.extractall(dest)
    found = list(dest.rglob("model.txt"))
    if not found:
        raise RuntimeError(f"Downloaded artefact for {version} has no model.txt")
    return found[0].parent


def publish_artefact(version_dir: Path) -> str | None:
    """Upload one version directory. A failure returns None and does not raise."""
    directory = Path(version_dir)
    if not directory.is_dir():
        return None
    try:
        uploaded = _supabase_upload(directory)
        if uploaded:
            return uploaded
        uploaded = _github_release(directory)
        if uploaded:
            return uploaded
    except (OSError, HTTPError, URLError, TimeoutError, ValueError) as exc:
        print(f"Model upload failed, metadata will still be saved: {exc}")
        return None
    return str(directory)


def _zip(directory: Path) -> Path:
    target = directory.parent / f"{directory.name}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(directory.parent).as_posix())
    return target


def _supabase_upload(directory: Path) -> str | None:
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not base or not key:
        return None
    bucket = os.environ.get("SUPABASE_MODEL_BUCKET", "models")
    _supabase_bucket(base, key, bucket)
    archive = _zip(directory)
    object_name = f"{directory.name}/{archive.name}"
    url = f"{base}/storage/v1/object/{bucket}/{object_name}"
    _request(
        "POST",
        url,
        archive.read_bytes(),
        {
            "Authorization": f"Bearer {key}",
            "apikey": key,
            "Content-Type": "application/zip",
            "x-upsert": "true",
        },
    )
    return url


def _supabase_bucket(base: str, key: str, bucket: str) -> None:
    try:
        _request(
            "POST",
            f"{base}/storage/v1/bucket",
            json.dumps({"id": bucket, "name": bucket, "public": False}).encode(),
            {
                "Authorization": f"Bearer {key}",
                "apikey": key,
                "Content-Type": "application/json",
            },
        )
    except HTTPError as exc:
        if exc.code not in (400, 409):
            raise


def _github_release(directory: Path) -> str | None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return None
    tag = f"model-{directory.name}"
    release = json.loads(
        _request(
            "POST",
            f"https://api.github.com/repos/{repo}/releases",
            json.dumps(
                {
                    "tag_name": tag,
                    "name": tag,
                    "body": "Versioned forecast model. Not a command to equipment.",
                    "make_latest": "false",
                }
            ).encode(),
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "rooftop-vpp",
            },
        )
    )
    archive = _zip(directory)
    upload_url = release["upload_url"].split("{", 1)[0]
    asset = json.loads(
        _request(
            "POST",
            f"{upload_url}?name={archive.name}",
            archive.read_bytes(),
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/zip",
                "User-Agent": "rooftop-vpp",
            },
        )
    )
    return asset.get("browser_download_url") or asset.get("url")


def _request(method: str, url: str, body: bytes, headers: dict) -> bytes:
    request = Request(url, data=body, headers=headers, method=method)
    with urlopen(request, timeout=60) as response:
        return response.read()
