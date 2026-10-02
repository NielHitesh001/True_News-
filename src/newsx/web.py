"""Local HTTP interface for the TrueNews editorial workspace.

The news pipeline remains the source of truth.  This module only serializes
its SQLite-backed records for the Stitch-inspired browser UI; it introduces no
new persistence format and has no third-party web-framework dependency.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .pipeline import Pipeline
from .presenter import HtmlBriefRenderer, MarkdownBriefRenderer
from .schemas import DisputedPoint


STATIC_DIR = Path(__file__).with_name("web_static")


def model_json(model: object) -> object:
    """Serialize Pydantic models and enums consistently across Pydantic 2."""
    if hasattr(model, "model_dump"):
        return getattr(model, "model_dump")(mode="json")
    return model


class NewsxApplication:
    def __init__(self) -> None:
        self.pipeline = Pipeline()

    @property
    def storage(self):
        return self.pipeline.storage

    def health(self) -> dict[str, object]:
        canonical_events = [event for event in self.storage.list_events() if event.id != "all"]
        return {
            "service": "TrueNews local editorial engine",
            "status": "ok",
            "events": len(canonical_events),
            "items": len(self.storage.list_items()),
            "ledger_entries": len(self.storage.list_ledger_entries()),
            "sources": len(self.pipeline.registry.all_sources()),
            "zero_cost_mode": True,
        }

    def events(self) -> list[dict[str, object]]:
        results: list[dict[str, object]] = []
        for event in self.storage.list_events():
            entries = self.storage.get_ledger_entries(event.id)
            disputed = sum(1 for entry in entries if entry.contradictions)
            results.append(
                {
                    "id": event.id,
                    "label": event.label,
                    "item_count": len(event.member_item_ids),
                    "claim_count": len(event.claim_ids),
                    "ledger_count": len(entries),
                    "dispute_count": disputed,
                    "time_span": [value.isoformat() if value else None for value in event.time_span],
                }
            )
        return results

    def event_or_error(self, event_id: str) -> dict[str, object]:
        event = self.storage.get_event(event_id)
        if not event:
            raise KeyError(f"Unknown event: {event_id}")
        return model_json(event)  # type: ignore[return-value]

    def brief(self, event_id: str) -> dict[str, object]:
        self.event_or_error(event_id)
        return model_json(self.pipeline.brief_generator.generate_brief(event_id))  # type: ignore[return-value]

    def claims(self, event_id: str) -> list[dict[str, object]]:
        event = self.storage.get_event(event_id)
        if not event:
            raise KeyError(f"Unknown event: {event_id}")
        return [model_json(claim) for claim_id in event.claim_ids if (claim := self.storage.get_claim(claim_id))]  # type: ignore[list-item]

    def ledger(self, event_id: str | None = None) -> list[dict[str, object]]:
        return [model_json(entry) for entry in self.storage.get_ledger_entries(event_id)]  # type: ignore[list-item]

    def sources(self) -> list[dict[str, object]]:
        return [model_json(source) for source in self.pipeline.registry.all_sources()]  # type: ignore[list-item]

    def export(self, event_id: str, extension: str) -> tuple[bytes, str, str]:
        brief = self.pipeline.brief_generator.generate_brief(event_id)
        if extension == "md":
            return MarkdownBriefRenderer().render(brief).encode("utf-8"), "text/markdown; charset=utf-8", f"{event_id}.md"
        if extension == "html":
            return HtmlBriefRenderer().render(brief).encode("utf-8"), "text/html; charset=utf-8", f"{event_id}.html"
        raise KeyError("Only .md and .html exports are available")


class NewsxHandler(BaseHTTPRequestHandler):
    application = NewsxApplication()

    def log_message(self, format: str, *args: object) -> None:
        # Keep terminal output focused on the pipeline, not every asset request.
        return

    def _send_json(self, body: object, status: int = HTTPStatus.OK) -> None:
        payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self, path: Path) -> None:
        if not path.is_file() or STATIC_DIR not in path.parents:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8" if content_type.startswith("text/") else content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        query = parse_qs(parsed.query)
        try:
            if path == "/api/health":
                self._send_json(self.application.health())
            elif path == "/api/events":
                self._send_json(self.application.events())
            elif path == "/api/sources":
                self._send_json(self.application.sources())
            elif path == "/api/ledger":
                self._send_json(self.application.ledger(query.get("event", [None])[0]))
            elif path.startswith("/api/events/") and path.endswith("/brief"):
                self._send_json(self.application.brief(path.removeprefix("/api/events/").removesuffix("/brief").strip("/")))
            elif path.startswith("/api/events/") and path.endswith("/claims"):
                self._send_json(self.application.claims(path.removeprefix("/api/events/").removesuffix("/claims").strip("/")))
            elif path.startswith("/api/exports/"):
                filename = path.removeprefix("/api/exports/")
                event_id, dot, extension = filename.rpartition(".")
                if not dot:
                    raise KeyError("Export extension required")
                data, content_type, download_name = self.application.export(event_id, extension)
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif path == "/" or path == "/index.html":
                self._send_file(STATIC_DIR / "index.html")
            elif path.startswith("/assets/"):
                self._send_file(STATIC_DIR / path.removeprefix("/"))
            else:
                self.send_error(HTTPStatus.NOT_FOUND)
        except KeyError as error:
            self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
        except Exception as error:  # pragma: no cover - guard for local UI diagnostics
            self._send_json({"error": "Internal server error", "detail": str(error)}, HTTPStatus.INTERNAL_SERVER_ERROR)


def serve(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), NewsxHandler)
    print(f"TrueNews web workspace running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nTrueNews web workspace stopped.")
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local TrueNews web workspace")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    serve(args.host, args.port)


if __name__ == "__main__":
    main()
