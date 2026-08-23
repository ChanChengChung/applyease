from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def _request(url: str, method: str):
    headers = {"User-Agent": "ApplyEase-LinkCheck/1.0", "Accept": "text/html,application/xhtml+xml"}
    if method == "GET":
        # Verify HEAD-hostile pages without downloading an entire resource.
        headers["Range"] = "bytes=0-0"
    return Request(url, method=method, headers=headers)


def check_resource_link(resource) -> str:
    """Check only curated catalogue URLs; no user-controlled URL is fetched."""
    parsed = urlparse(resource.url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        resource.link_status = "broken"
        resource.last_checked_at = datetime.now(timezone.utc)
        return resource.link_status

    try:
        with urlopen(_request(resource.url, "HEAD"), timeout=10) as response:
            status = getattr(response, "status", 200)
    except HTTPError as exc:
        if exc.code not in {405, 501}:
            status = exc.code
        else:
            try:
                with urlopen(_request(resource.url, "GET"), timeout=10) as response:
                    status = getattr(response, "status", 200)
            except HTTPError as fallback_error:
                status = fallback_error.code
            except Exception:
                status = 0
    except Exception:
        status = 0

    resource.link_status = "healthy" if 200 <= status < 400 else "broken"
    resource.last_checked_at = datetime.now(timezone.utc)
    return resource.link_status
