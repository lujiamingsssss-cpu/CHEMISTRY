"""Acceptance tests for scripts/dev_preview.py.

The preview script exists because the onboarding guide tells readers that static
pages must be served over HTTP and never through file://, but only provides a raw
``python -m http.server`` command. These tests pin the observable contract:
resolvable preview targets and a real HTML response over HTTP.
"""

import http.client
import importlib.util
import sys
import threading
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/dev_preview.py"
HOMEPAGE = "/showcase/homepage/index.html"


def _module():
    spec = importlib.util.spec_from_file_location("dev_preview", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # Register before exec so dataclasses can resolve the module by name.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_preview_targets_expose_the_showcase_homepage():
    module = _module()

    targets = module.resolve_preview_targets(REPO)

    assert HOMEPAGE in {target.url_path for target in targets}


def test_preview_targets_only_list_paths_that_exist(tmp_path):
    module = _module()

    targets = module.resolve_preview_targets(tmp_path)

    assert all(not (tmp_path / target.url_path.lstrip("/")).exists() for target in targets)
    assert all(target.available is False for target in targets)


def test_served_homepage_is_html_over_http():
    module = _module()
    server = module.build_server(REPO, host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=30)
        try:
            connection.request("GET", HOMEPAGE)
            response = connection.getresponse()
            body = response.read()
            assert response.status == 200
            assert response.getheader("Content-Type", "").startswith("text/html")
            assert b"<html" in body.lower()
        finally:
            connection.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=30)


def test_cli_reports_targets_without_starting_a_server(capsys):
    module = _module()

    exit_code = module.main(["--print-only"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert HOMEPAGE in captured.out


def test_open_target_prefers_the_first_available_page():
    module = _module()
    missing = module.PreviewTarget(label="missing", url_path="/missing.html", available=False)
    ready = module.PreviewTarget(label="ready", url_path="/ready.html", available=True)

    assert module.choose_open_target((missing, ready)).url_path == "/ready.html"


def test_open_target_is_none_when_no_page_exists(tmp_path):
    module = _module()

    assert module.choose_open_target(module.resolve_preview_targets(tmp_path)) is None


def test_serving_opens_the_available_page_in_a_browser(monkeypatch):
    module = _module()
    opened = []
    monkeypatch.setattr(module, "open_in_browser", lambda url: opened.append(url) or True)
    monkeypatch.setattr(module, "serve_until_interrupted", lambda server: None)

    exit_code = module.main(["--port", "0"])

    assert exit_code == 0
    assert len(opened) == 1
    assert opened[0].endswith(HOMEPAGE)


def test_no_open_flag_suppresses_the_browser(monkeypatch):
    module = _module()
    opened = []
    monkeypatch.setattr(module, "open_in_browser", lambda url: opened.append(url) or True)
    monkeypatch.setattr(module, "serve_until_interrupted", lambda server: None)

    exit_code = module.main(["--port", "0", "--no-open"])

    assert exit_code == 0
    assert opened == []


def test_print_only_never_opens_a_browser(monkeypatch):
    module = _module()
    opened = []
    monkeypatch.setattr(module, "open_in_browser", lambda url: opened.append(url) or True)

    assert module.main(["--print-only"]) == 0
    assert opened == []


def test_resolve_root_defaults_to_this_checkout():
    module = _module()

    assert module.resolve_root(None) == REPO


def test_resolve_root_uses_the_given_directory(tmp_path):
    module = _module()

    assert module.resolve_root(str(tmp_path)) == tmp_path


def test_root_option_is_honoured_when_choosing_what_to_open(monkeypatch, tmp_path):
    """A root without the showcase page must stay silent even though this checkout has one."""

    module = _module()
    opened = []
    monkeypatch.setattr(module, "open_in_browser", lambda url: opened.append(url) or True)
    monkeypatch.setattr(module, "serve_until_interrupted", lambda server: None)

    assert module.main(["--root", str(tmp_path), "--port", "0"]) == 0
    assert opened == []


def test_missing_root_is_rejected(tmp_path, capsys):
    module = _module()

    with pytest.raises(SystemExit):
        module.main(["--root", str(tmp_path / "does-not-exist"), "--print-only"])

    # Guard against a vacuous pass: rejecting an unknown option would also exit,
    # so require the message only a real missing-directory check produces.
    assert "not a directory" in capsys.readouterr().err
