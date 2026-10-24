"""Cover the CI workflow's safety properties: Windows runner, read-only token, no secrets, no publishing.

Behavior covered: ``.github/workflows/validate.yml`` runs on ``windows-latest``, grants only
``contents: read``, uses no secret, never checks out with stored credentials, uses no
``pull_request_target`` trigger, never commits or pushes, and runs the package checker, the registry
rules and the tracker fixtures.
Real: the workflow file, read as text (no YAML library is needed or assumed). Out of scope: running
it on GitHub.
"""

from __future__ import annotations

import re

import pytest

from _tests.conftest import REGISTRY_ROOT

WORKFLOW = (REGISTRY_ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")


def test_the_workflow_runs_on_a_windows_runner() -> None:
    """Every job runs on ``windows-latest`` and no other runner is named."""
    assert re.findall(r"(?m)^\s*runs-on:\s*(\S+)", WORKFLOW) == ["windows-latest"]


def test_the_token_is_read_only() -> None:
    """The only permission is ``contents: read`` and nothing grants write access."""
    assert re.search(r"(?m)^permissions:\n  contents: read\n", WORKFLOW)
    assert not re.search(r":\s*write\b", WORKFLOW)


@pytest.mark.parametrize(
    "forbidden",
    [
        pytest.param(r"secrets\.", id="secrets"),
        pytest.param(r"pull_request_target", id="pull_request_target"),
        pytest.param(r"git\s+(push|commit)", id="git-push-or-commit"),
        pytest.param(r"--auto-push", id="auto-push"),
        pytest.param(r"GITHUB_TOKEN", id="token-variable"),
    ],
)
def test_the_workflow_never_uses(forbidden: str) -> None:
    """The workflow contains no secret, no privileged trigger and no way to publish."""
    assert not re.search(forbidden, WORKFLOW)


def test_every_checkout_drops_its_credentials() -> None:
    """Each ``actions/checkout`` step sets ``persist-credentials: false``."""
    assert WORKFLOW.count("actions/checkout@") == WORKFLOW.count("persist-credentials: false") >= 2


def test_the_workflow_runs_every_check_the_issue_requires() -> None:
    """Package checker over all packages, the registry rules, the registry tests and the tracker fixtures all run."""
    for command in ("_tools/pkg_check.py --all", "_tools/registry_tool.py validate", "pytest -q _tests", "test_track_providers.py"):
        assert command in WORKFLOW
