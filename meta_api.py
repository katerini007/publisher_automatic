"""
Thin wrapper around the Meta/Instagram Graph API content publishing flow.
No third-party posting SDKs — just requests, direct to Meta's servers.

Flow implemented (per developers.facebook.com/docs/instagram-platform/content-publishing):
  1. POST /{ig_user_id}/media          -> create a container (resumable upload session
                                           for local files, or a direct video_url/image_url)
  2. POST rupload.facebook.com/...     -> upload the local file's bytes (video only)
  3. GET  /{container_id}?fields=status_code  -> poll until FINISHED
  4. POST /{ig_user_id}/media_publish  -> publish the container

SECURITY: credentials are read from environment variables and passed through
as request params/headers only. They are never written to a log, printed to
the console, or included in any exception message raised from this module.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any

import requests

# Instagram API with Instagram Login (IGAA... tokens) — NOT the Facebook-login
# Graph API. Uses graph.instagram.com and the token's own account via "me".
API_VERSION = "v23.0"
GRAPH_HOST = "https://graph.instagram.com"
RUPLOAD_HOST = "https://rupload.instagram.com"

# Only the token is truly required for publishing via Instagram Login. The
# account is addressed as "me" (whoever owns the token), so the numeric
# account id is optional. App id/secret aren't needed for content publishing.
REQUIRED_ENV = [
    "META_PAGE_ACCESS_TOKEN",
]


class MetaAPIError(RuntimeError):
    """Raised on any Graph API failure. Message is scrubbed of secrets."""


class Credentials:
    __slots__ = ("page_access_token", "ig_user_id")

    def __init__(self, page_access_token, ig_user_id="me"):
        self.page_access_token = page_access_token
        # Address the account as "me" by default so the exact numeric id never
        # matters (Instagram Login and Facebook Login report different ids for
        # the same account).
        self.ig_user_id = ig_user_id or "me"


def load_credentials() -> Credentials:
    """Read + validate required env vars. Raises with a helpful message that
    names which keys are missing — never includes their values."""
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise MetaAPIError(
            f"Missing env vars: {missing}. Copy .env.example to .env and fill them in."
        )
    return Credentials(
        page_access_token=os.environ["META_PAGE_ACCESS_TOKEN"],
        ig_user_id="me",
    )


def _auth_header(creds: Credentials) -> Dict[str, str]:
    # Bearer-header auth throughout, instead of an access_token query/body
    # param, so the token never ends up in a URL (and therefore never in a
    # stack trace, proxy log, or exception message triggered by a network error).
    return {"Authorization": f"Bearer {creds.page_access_token}"}


def _raise_for_response(resp: requests.Response, context: str) -> None:
    if resp.ok:
        return
    try:
        body = resp.json()
        detail = body.get("error", {}).get("message", resp.text)
    except ValueError:
        detail = resp.text
    raise MetaAPIError(f"{context} failed ({resp.status_code}): {detail}")


def _request(method: str, url: str, *, context: str, **kwargs) -> requests.Response:
    """Wraps requests calls so network-level exceptions never bubble up with
    raw request internals (which could echo back headers/params) in the message."""
    try:
        resp = requests.request(method, url, **kwargs)
    except requests.exceptions.RequestException as e:
        raise MetaAPIError(f"{context}: network error ({type(e).__name__})") from None
    _raise_for_response(resp, context)
    return resp


def create_container(
    creds: Credentials,
    caption: str,
    media_type: str,
    *,
    video_path: Optional[str] = None,
    image_path: Optional[str] = None,
    video_url: Optional[str] = None,
    image_url: Optional[str] = None,
    trial: bool = False,
    graduation_strategy: str = "MANUAL",
) -> str:
    """
    Create a media container. Returns the container id.

    For local files (video_path/image_path) this opens a resumable upload
    session (upload_type=resumable) — the actual bytes are sent separately
    via upload_video_resumable(). For *_url inputs, Meta fetches the file
    itself and the container is ready to poll/publish directly.

    trial=True publishes a Trial Reel (shown only to non-followers first).
    graduation_strategy: "MANUAL" (you graduate it in-app) or "SS_PERFORMANCE"
    (auto-graduates to followers if it performs well). Trial reels require
    media_type=REELS.
    """
    url = f"{GRAPH_HOST}/{API_VERSION}/{creds.ig_user_id}/media"
    params: Dict[str, Any] = {
        "caption": caption,
        "media_type": media_type,
    }

    if trial:
        if media_type != "REELS":
            raise MetaAPIError("Trial reels require media_type=REELS")
        params["trial_params"] = json.dumps({"graduation_strategy": graduation_strategy})

    using_local_upload = bool(video_path) and not video_url
    if using_local_upload:
        params["upload_type"] = "resumable"
    elif video_url:
        params["video_url"] = video_url
    elif image_url:
        params["image_url"] = image_url
    elif image_path:
        # Image containers don't support resumable upload — require a public URL.
        raise MetaAPIError(
            "Local image uploads aren't supported by the Graph API; "
            "host the image and pass --image-url instead."
        )
    else:
        raise MetaAPIError("create_container: no media source provided")

    resp = _request("POST", url, context="Create container", data=params, headers=_auth_header(creds), timeout=60)
    return resp.json()["id"]


def upload_video_resumable(creds: Credentials, container_id: str, file_path: str) -> None:
    """Upload a local video file's bytes to an already-created resumable container."""
    path = Path(file_path)
    if not path.exists():
        raise MetaAPIError(f"Video file not found: {file_path}")

    file_size = path.stat().st_size
    url = f"{RUPLOAD_HOST}/ig-api-upload/{API_VERSION}/{container_id}"
    headers = {
        "Authorization": f"OAuth {creds.page_access_token}",
        "offset": "0",
        "file_size": str(file_size),
    }
    with path.open("rb") as f:
        resp = _request("POST", url, context="Video upload", headers=headers, data=f, timeout=600)
    body = resp.json()
    if not body.get("success"):
        raise MetaAPIError(f"Video upload did not report success: {body}")


def get_container_status(creds: Credentials, container_id: str) -> str:
    url = f"{GRAPH_HOST}/{API_VERSION}/{container_id}"
    resp = _request(
        "GET", url, context="Container status check",
        params={"fields": "status_code"}, headers=_auth_header(creds), timeout=30,
    )
    return resp.json().get("status_code", "UNKNOWN")


def wait_for_finished(
    creds: Credentials, container_id: str, timeout_sec: int = 280, poll_interval_sec: int = 10
) -> None:
    """Poll status_code until FINISHED. Raises on ERROR/EXPIRED or timeout."""
    elapsed = 0
    while elapsed < timeout_sec:
        status = get_container_status(creds, container_id)
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise MetaAPIError(f"Container processing failed: status={status}")
        time.sleep(poll_interval_sec)
        elapsed += poll_interval_sec
    raise MetaAPIError(f"Timed out waiting for container to finish processing ({timeout_sec}s)")


def publish_container(creds: Credentials, container_id: str) -> str:
    """Publish a ready container. Returns the published media id."""
    url = f"{GRAPH_HOST}/{API_VERSION}/{creds.ig_user_id}/media_publish"
    resp = _request(
        "POST", url, context="Publish",
        data={"creation_id": container_id}, headers=_auth_header(creds), timeout=60,
    )
    return resp.json()["id"]


def get_permalink(creds: Credentials, media_id: str) -> Optional[str]:
    url = f"{GRAPH_HOST}/{API_VERSION}/{media_id}"
    try:
        resp = _request(
            "GET", url, context="Permalink lookup",
            params={"fields": "permalink"}, headers=_auth_header(creds), timeout=30,
        )
    except MetaAPIError:
        return None
    return resp.json().get("permalink")


def check_publishing_limit(creds: Credentials) -> Dict[str, Any]:
    """Instagram caps API-published posts at 100 per rolling 24h window."""
    url = f"{GRAPH_HOST}/{API_VERSION}/{creds.ig_user_id}/content_publishing_limit"
    resp = _request("GET", url, context="Rate limit check", headers=_auth_header(creds), timeout=30)
    data = resp.json().get("data", [])
    return data[0] if data else {}
