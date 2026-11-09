import ssl
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def normalize_celery_redis_url(raw_url: str) -> tuple[str, dict[str, ssl.VerifyMode]]:
    if not raw_url.startswith("rediss://"):
        return raw_url, {}

    parts = urlsplit(raw_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    cert_reqs = (query.pop("ssl_cert_reqs", "required") or "required").lower()
    normalized_url = urlunsplit(parts._replace(query=urlencode(query)))

    ssl_options = {
        "required": ssl.CERT_REQUIRED,
        "optional": ssl.CERT_OPTIONAL,
        "none": ssl.CERT_NONE,
        "cert_required": ssl.CERT_REQUIRED,
        "cert_optional": ssl.CERT_OPTIONAL,
        "cert_none": ssl.CERT_NONE,
    }
    return normalized_url, {"ssl_cert_reqs": ssl_options.get(cert_reqs, ssl.CERT_REQUIRED)}
