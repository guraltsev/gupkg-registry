"""Cover the fixture recorder: it records the whole tracker walk and never half-writes a case.

``_tools/record_http_fixtures.py`` re-records a case of ``_tests/fixtures/http`` by running the package's live tracker against the
vendor's site and writing down every request and answer. Here the site is a ``FakeSystem`` (no network).

Rules covered: a re-recording replaces the visited responses, keeps only the headers a provider reads (no cookies or server
banners), and rewrites the date, the origin note and the ``expected`` block; an index walk is recorded page by page and pages the
walk no longer visits are dropped; a run that fails, even after the client's retries, leaves the case file as it was; a dry run
requests but writes nothing. Out of scope: talking to the real sites, which is a manual step (README, "Tracker fixtures").
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from _tests.support import HTTP_CASES, FakeHttp, FakeSystem, serve_pidgin_without_the_newest_installer
from _tools import record_http_fixtures


def copy_case(tmp_path: Path, name: str) -> Path:
    """Copy a committed fixture case into *tmp_path* and return the copy."""
    target = tmp_path / f"{name}.json"
    shutil.copyfile(HTTP_CASES / f"{name}.json", target)
    return target


def test_recording_rewrites_the_responses_and_the_expected_block(system: FakeSystem, tmp_path: Path) -> None:
    """A new `Last-Modified` on the live site becomes the case's response, its version and a recording date; secrets are not kept."""
    case = copy_case(tmp_path, "last_modified_autoruns")
    url = json.loads(case.read_text(encoding="utf-8"))["responses"][0]["url"]
    system.urls[url] = FakeHttp("", 200, {"Last-Modified": "Mon, 07 Oct 2024 10:00:00 GMT", "Set-Cookie": "secret=1", "Server": "x"})

    lines = record_http_fixtures.record_case(case, system)

    document = json.loads(case.read_text(encoding="utf-8"))
    assert document["responses"][0]["headers"] == {"last-modified": "Mon, 07 Oct 2024 10:00:00 GMT", "content-length": "0"}
    assert document["expected"]["version"] == "20241007"
    assert document["recorded"] and document["origin"].startswith("recorded from the live sites")
    assert lines == [f"HEAD {url} -> 200, 0 bytes"]
    assert system.request_log[0].headers["User-Agent"] == "gupkg-fixture-recorder/1"


def test_an_index_walk_is_recorded_page_by_page_and_unvisited_pages_are_dropped(system: FakeSystem, tmp_path: Path) -> None:
    """Re-recording pidgin records the root listing and the two folders the walk visits (the newest has no installer), and drops a stale extra URL."""
    case = copy_case(tmp_path, "index_pidgin")
    document = json.loads(case.read_text(encoding="utf-8"))
    document["responses"].append({"url": "https://example.org/stale", "method": "GET", "status": 200, "headers": {}, "body": "old"})
    case.write_text(json.dumps(document), encoding="utf-8")
    newest, previous = serve_pidgin_without_the_newest_installer(system)

    record_http_fixtures.record_case(case, system)

    recorded = json.loads(case.read_text(encoding="utf-8"))
    urls = [entry["url"] for entry in recorded["responses"]]
    root = "https://sourceforge.net/projects/pidgin/files/Pidgin/"
    assert urls == [root, f"{root}{newest}/", f"{root}{previous}/"]
    assert recorded["expected"]["version"] == previous


def test_a_failing_run_leaves_the_case_file_untouched(system: FakeSystem, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """If a URL cannot be fetched, even after the client's retries, nothing is written: the old, working fixture stays."""
    case = copy_case(tmp_path, "last_modified_autoruns")
    before = case.read_bytes()
    url = json.loads(case.read_text(encoding="utf-8"))["responses"][0]["url"]
    system.urls[url] = ConnectionResetError("reset")
    waits: list[float] = []
    monkeypatch.setattr(record_http_fixtures.time, "sleep", waits.append)  # the client's retry delays, without waiting

    with pytest.raises(Exception):
        record_http_fixtures.record_case(case, system)

    assert waits, "the failed request was retried before the run gave up"
    assert case.read_bytes() == before


def test_a_dry_run_requests_but_writes_nothing(system: FakeSystem, tmp_path: Path) -> None:
    """With `write=False` the requests are reported and the file is unchanged."""
    case = copy_case(tmp_path, "last_modified_autoruns")
    before = case.read_bytes()
    url = json.loads(case.read_text(encoding="utf-8"))["responses"][0]["url"]
    system.urls[url] = FakeHttp("", 200, {"Last-Modified": "Mon, 07 Oct 2024 10:00:00 GMT"})

    lines = record_http_fixtures.record_case(case, system, write=False)

    assert lines and case.read_bytes() == before
