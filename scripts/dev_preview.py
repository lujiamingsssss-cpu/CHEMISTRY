"""Serve the repository's static showcase over HTTP for local preview.

Static pages must be reached through an HTTP server: opening them from ``file://``
relies on incidental browser behaviour and is not a supported contract (see
``docs/PROJECT_ONBOARDING.md``). This script replaces the hand-typed
``python -m http.server`` invocation with one that always serves the repository
root and prints the URLs to open.

It is deliberately read-only: it never writes to the repository.
"""

import argparse
import functools
import threading
import webbrowser
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Sequence


SHOWCASE_HOMEPAGE = "/showcase/homepage/index.html"
H2_REVIEW_PAGE = "/output/twinkle-stage5-h2-full-flow-review/index.html"

# Explicit map so responses do not depend on the host's mime registry.
_EXTENSION_MAP = {
    **SimpleHTTPRequestHandler.extensions_map,
    ".html": "text/html",
    ".css": "text/css",
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".json": "application/json",
    ".png": "image/png",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}


@dataclass(frozen=True)
class PreviewTarget:
    """A page worth opening, and whether this checkout actually contains it."""

    label: str
    url_path: str
    available: bool


class PreviewRequestHandler(SimpleHTTPRequestHandler):
    """Static handler with a deterministic extension map."""

    extensions_map = _EXTENSION_MAP


def repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve_preview_targets(repo: Path) -> tuple[PreviewTarget, ...]:
    """Return the previewable pages, marking the ones absent from this checkout."""

    repo = Path(repo)
    candidates = (
        ("showcase 首页", SHOWCASE_HOMEPAGE),
        ("TWINKLE H2 审核页", H2_REVIEW_PAGE),
    )
    return tuple(
        PreviewTarget(
            label=label,
            url_path=url_path,
            available=(repo / url_path.lstrip("/")).is_file(),
        )
        for label, url_path in candidates
    )


def build_server(repo: Path, host: str, port: int) -> ThreadingHTTPServer:
    """Build (but do not start) a server rooted at ``repo``."""

    handler = functools.partial(PreviewRequestHandler, directory=str(Path(repo).resolve()))
    return ThreadingHTTPServer((host, port), handler)


def _format_targets(targets: Sequence[PreviewTarget], host: str, port: int) -> list[str]:
    lines = []
    for target in targets:
        suffix = "" if target.available else "  (本机不存在，跳过)"
        lines.append(f"{target.label}: http://{host}:{port}{target.url_path}{suffix}")
    return lines


def choose_open_target(targets: Sequence[PreviewTarget]) -> PreviewTarget | None:
    """Pick the page to open automatically, or ``None`` when no page exists."""

    for target in targets:
        if target.available:
            return target
    return None


def open_in_browser(url: str) -> bool:
    """Open ``url`` in the default browser. Isolated so tests can replace it."""

    return webbrowser.open(url)


def serve_until_interrupted(server: ThreadingHTTPServer) -> None:
    """Serve in a background thread so the caller can act right after binding."""

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        while thread.is_alive():
            thread.join(timeout=0.5)
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.shutdown()
        server.server_close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Serve the static showcase over HTTP for local preview.",
    )
    parser.add_argument("--bind", default="127.0.0.1", help="interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="port to bind (default: 8000)")
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="print the preview URLs and exit without starting a server",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="serve without opening the default browser",
    )
    args = parser.parse_args(argv)

    repo = repository_root()
    targets = resolve_preview_targets(repo)
    for line in _format_targets(targets, args.bind, args.port):
        print(line)

    if args.print_only:
        return 0

    server = build_server(repo, args.bind, args.port)
    port = server.server_address[1]
    print(f"\n服务根目录 {repo}，按 Ctrl+C 停止。")

    target = choose_open_target(targets)
    if target is not None and not args.no_open:
        url = f"http://{args.bind}:{port}{target.url_path}"
        if not open_in_browser(url):
            print(f"未能自动打开浏览器，请手动访问：{url}")
    elif target is None:
        print("没有任何可预览页面（本机缺少对应文件）。")

    serve_until_interrupted(server)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
