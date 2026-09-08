"""Bounded health checks for curated learning-resource links."""

from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.models.resource import LearningResource


def _request(url: str, method: str) -> Request:
    return Request(
        url,
        method=method,
        headers={"User-Agent": "ApplyEase-resource-health/1.0"},
    )


def _probe(url: str, method: str) -> int:
    with urlopen(_request(url, method), timeout=5) as response:  # nosec B310: scheme is checked below
        status = getattr(response, "status", None)
        if status is None:
            status = response.getcode()
        return int(status)


def check_url(url: str) -> tuple[bool, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "unsupported_url"
    try:
        status = _probe(url, "HEAD")
    except HTTPError as exc:
        # Some otherwise healthy hosts reject HEAD. A single bounded GET is a
        # deliberate fallback; we never follow arbitrary redirects ourselves.
        if exc.code not in {405, 501}:
            return False, f"http_{exc.code}"
        try:
            status = _probe(url, "GET")
        except (OSError, URLError, ValueError):
            return False, "network_error"
    except (OSError, URLError, ValueError):
        return False, "network_error"
    return status < 400, f"http_{status}"


def update_resource_health(db: Session, resource: LearningResource) -> LearningResource:
    healthy, _reason = check_url(resource.url)
    resource.link_status = "healthy" if healthy else "broken"
    resource.last_checked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(resource)
    return resource
