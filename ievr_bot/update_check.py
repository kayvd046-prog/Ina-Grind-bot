"""Check GitHub for a newer release. Fails silently — never bothers the user
when offline or rate-limited."""
import json
import re
import urllib.request
from typing import Callable, Optional

DEFAULT_URL = ("https://api.github.com/repos/kayvd046-prog/Ina-Grind-bot/"
               "releases/latest")


def parse_version(tag) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", tag or ""))


def is_newer(latest_tag, current: str) -> bool:
    latest = parse_version(latest_tag)
    return bool(latest) and latest > parse_version(current)


def _default_fetcher(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.read()


def fetch_latest(url: str = DEFAULT_URL,
                 fetcher: Optional[Callable[[str], bytes]] = None
                 ) -> Optional[tuple[str, str]]:
    """Return ``(tag, release page url)`` of the newest release, or None."""
    fetcher = fetcher or _default_fetcher
    try:
        data = json.loads(fetcher(url))
        return (data["tag_name"], data["html_url"])
    except Exception:
        return None
