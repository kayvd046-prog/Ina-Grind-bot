"""Update check: compare the newest GitHub release tag with our version."""
import json
from ievr_bot.update_check import parse_version, is_newer, fetch_latest


def test_parse_version_handles_v_prefix_and_partial_tags():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("1.10") == (1, 10)
    assert parse_version("garbage") == ()
    assert parse_version(None) == ()


def test_is_newer_compares_semantically():
    assert is_newer("v1.2.0", "1.1.0")
    assert is_newer("v1.10.0", "1.9.9")   # numeric, not lexicographic
    assert not is_newer("v1.1.0", "1.1.0")
    assert not is_newer("v1.0.9", "1.1.0")
    assert not is_newer("garbage", "1.1.0")
    assert not is_newer(None, "1.1.0")


def test_fetch_latest_parses_github_release_json():
    payload = json.dumps({
        "tag_name": "v9.9.9",
        "html_url": "https://github.com/kayvd046-prog/Ina-Grind-bot/releases/tag/v9.9.9",
    }).encode()
    got = fetch_latest(fetcher=lambda url: payload)
    assert got == ("v9.9.9",
                   "https://github.com/kayvd046-prog/Ina-Grind-bot/releases/tag/v9.9.9")


def test_fetch_latest_returns_none_on_any_failure():
    def broken(url):
        raise OSError("offline")

    assert fetch_latest(fetcher=broken) is None
    assert fetch_latest(fetcher=lambda url: b"not json") is None
    assert fetch_latest(fetcher=lambda url: b"{}") is None
