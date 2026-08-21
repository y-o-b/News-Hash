from __future__ import annotations

import html
import mimetypes
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, unquote, urlencode, urlparse

import markdown

from newshash.anchoring import OpenTimestampsAnchor
from newshash.settings import AppConfig, SettingsManager
from newshash.storage import SqliteStorage

THEMES = {"comic", "dark", "lite", "paper", "news"}
PAGE_SIZES = (10, 25, 50, 100)
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="News-Hash">
<rect width="128" height="128" rx="24" fill="#4b8ed8"/>
<path d="M25 91 43 29h18L43 91H25Zm42 0 18-62h18L85 91H67Z" fill="#171717"/>
<path d="M20 57h88v14H20V57Zm-5 25h88v14H15V82Z" fill="#ef4b3f" stroke="#171717" stroke-width="4"/>
</svg>"""
LOGO_PAPER_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" role="img" aria-label="News-Hash">
<path d="M25 91 43 29h18L43 91H25Zm42 0 18-62h18L85 91H67Z" fill="#29251f"/>
<path d="M20 57h88v14H20V57Zm-5 25h88v14H15V82Z" fill="#9d3029" stroke="#29251f" stroke-width="4"/>
</svg>"""


@dataclass(frozen=True)
class SourceSummary:
    name: str
    storage_name: str
    records: int
    images: int
    latest_retrieved_at: str
    latest_hash: str
    errors: int = 0
    last_error: str = ""
    anchored_today: bool = False
    anchor_status: str = "no_anchor"
    anchor_date: str = ""
    anchor_manifest_exists: bool = False
    anchor_proof_exists: bool = False
    sqlite_size_bytes: int = 0


def _timestamp(value: Any) -> datetime:
    """Parse ISO- oder RFC-Datumswerte als vergleichbaren UTC-Zeitpunkt."""

    text = str(value or "")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except TypeError, ValueError, OverflowError:
            return datetime.min.replace(tzinfo=UTC)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _record_sort_key(record: dict[str, Any]) -> tuple[int, datetime]:
    published_at = record.get("published_at")
    if published_at:
        return 1, _timestamp(published_at)
    return 0, _timestamp(record.get("retrieved_at"))


def collect_dashboard_data(
    config: AppConfig,
    settings_manager: SettingsManager,
    selected_source: str | None = None,
    page: int = 1,
    page_size: int = 10,
) -> dict[str, Any]:
    """Lese Kennzahlen und die neuesten Meldungen aus den Quellen-Stores."""

    page = max(1, page)
    summaries: list[SourceSummary] = []
    latest_records: list[dict[str, Any]] = []
    selected_records = 0
    error_counts = settings_manager.unacknowledged_source_error_counts()
    error_messages = settings_manager.unacknowledged_source_errors()
    anchor = OpenTimestampsAnchor(settings_manager.storage_root())
    anchor_statuses = settings_manager.anchor_statuses()
    today = datetime.now(UTC).date()
    for source in config.settings.sources:
        storage = SqliteStorage(settings_manager.storage_root(), source.storage_name)
        stats = storage.dashboard_stats()
        summaries.append(
            SourceSummary(
                name=source.name,
                storage_name=source.storage_name,
                records=stats["records"],
                images=stats["images"],
                latest_retrieved_at=stats["latest_retrieved_at"],
                latest_hash=stats["latest_hash"],
                errors=error_counts.get(source.name, 0),
                last_error=(error_messages.get(source.name) or [""])[-1],
                anchored_today=anchor.proof_path(source).exists(),
                anchor_status=anchor_statuses.get(source.name, "no_anchor"),
                anchor_date=today.isoformat(),
                anchor_manifest_exists=anchor.manifest_path(source, today).exists(),
                anchor_proof_exists=anchor.proof_path(source, today).exists(),
                sqlite_size_bytes=storage.size_bytes(),
            )
        )
        if selected_source in {source.name, source.storage_name} or selected_source is None:
            selected_records += storage.latest_count()
            for record in storage.latest_records(page * page_size):
                latest_records.append({**record, "source_name": source.name, "storage_name": source.storage_name})

    if selected_source is None and len(config.settings.sources) > 1:
        latest_records.sort(key=_record_sort_key, reverse=True)
    start = (page - 1) * page_size
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": summaries,
        "records": latest_records[start : start + page_size],
        "total_records": sum(summary.records for summary in summaries),
        "total_images": sum(summary.images for summary in summaries),
        "runtime_logs": settings_manager.runtime_logs(),
        "selected_source": selected_source,
        "selected_records": selected_records,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (selected_records + page_size - 1) // page_size),
    }


def _text(value: Any, fallback: str = "-") -> str:
    return html.escape(str(value or fallback))


def _number(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def _data_size(value: int) -> str:
    """Formatiere eine Byte-Anzahl kompakt für die Quellenübersicht."""

    size = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            formatted = f"{size:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            return f"{formatted} {unit}"
        size /= 1024
    return "0 B"


def _media_url(storage_name: str, relative_path: str) -> str:
    """Erzeuge eine quellenbezogene URL für ein gespeichertes Bild."""

    return f"/media/{quote(storage_name, safe='')}/{quote(relative_path, safe='/')}"


def _query(params: dict[str, Any]) -> str:
    return html.escape(urlencode(params), quote=True)


def _local_time(value: Any) -> str:
    text = _text(value)
    return f'<time class="local-time" datetime="{text}">{text}</time>'


def _runtime_log_markup(entry: str) -> str:
    timestamp, separator, message = entry.partition(" ")
    if not separator:
        return f"<li>{_text(entry)}</li>"
    local_time = _local_time(timestamp).replace('class="local-time"', 'class="local-time log-time"', 1)
    return f"<li>{local_time} {_text(message)}</li>"


def _anchor_label(status: str) -> str:
    return {
        "no_anchor": "○ Kein Anchor",
        "no_ots": "○ Keine .ots-Datei",
        "pending": "◷ Attestation ausstehend",
        "complete": "✓ Vollständig bestätigt",
    }.get(status, "○ Unbekannt")


def _anchor_url(storage_name: str, anchor_date: str, kind: str) -> str:
    return f"/anchor/{quote(storage_name, safe='')}/{quote(anchor_date, safe='')}/{quote(kind, safe='')}"


def _anchor_links(source: SourceSummary) -> str:
    links: list[str] = []
    if source.anchor_manifest_exists:
        links.append(f'<a href="{_anchor_url(source.storage_name, source.anchor_date, "manifest")}">Manifest</a>')
    if source.anchor_proof_exists:
        links.append(f'<a href="{_anchor_url(source.storage_name, source.anchor_date, "proof")}">.ots</a>')
    return f'<span class="anchor-files"> · {" · ".join(links)}</span>' if links else ""


def _acknowledge_error_form(storage_name: str, theme_query: dict[str, Any]) -> str:
    """Erzeuge die Aktion zum Quittieren der offenen Fehler einer Quelle."""

    return (
        f'<form method="post" action="/acknowledge-error?{_query({"source": storage_name, **theme_query})}">'
        '<button class="acknowledge-button" type="submit">Fehler quittieren</button></form>'
    )


def _source_error_markup(source: SourceSummary, theme_query: dict[str, Any]) -> str:
    """Erzeuge Fehlermeldung und Quittierungsaktion für eine Quelle."""

    if not source.last_error:
        return ""
    return f'<div class="source-error">{_text(source.last_error)}</div>{_acknowledge_error_form(source.storage_name, theme_query)}'


def _detail_url(record: dict[str, Any]) -> str:
    storage_name = quote(record.get("storage_name", ""), safe="")
    source_id = quote(record.get("source_id", ""), safe="")
    theme = record.get("theme", "lite")
    return f"/meldung/{storage_name}/{source_id}?theme={quote(str(theme), safe='')}"


def _prometheus_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def render_metrics(config: AppConfig, settings_manager: SettingsManager) -> str:
    """Erzeuge Prometheus-Metriken aus aggregierten SQLite-Abfragen."""

    lines = [
        "# HELP newshash_sources_total Number of configured news sources.",
        "# TYPE newshash_sources_total gauge",
        f"newshash_sources_total {len(config.settings.sources)}",
        "# HELP newshash_records_total Number of stored records per source.",
        "# TYPE newshash_records_total gauge",
        "# HELP newshash_images_total Number of stored images per source.",
        "# TYPE newshash_images_total gauge",
        "# HELP newshash_source_errors_total Number of unacknowledged source errors.",
        "# TYPE newshash_source_errors_total counter",
    ]
    total_records = 0
    total_images = 0
    total_errors = 0
    error_counts = settings_manager.unacknowledged_source_error_counts()
    for source in config.settings.sources:
        stats = SqliteStorage(settings_manager.storage_root(), source.storage_name).dashboard_stats()
        label = _prometheus_label(source.name)
        lines.append(f'newshash_records_total{{source="{label}"}} {stats["records"]}')
        lines.append(f'newshash_images_total{{source="{label}"}} {stats["images"]}')
        errors = error_counts.get(source.name, 0)
        lines.append(f'newshash_source_errors_total{{source="{label}"}} {errors}')
        total_records += stats["records"]
        total_images += stats["images"]
        total_errors += errors
    lines.extend(
        [
            "# HELP newshash_records_all_total Total number of stored records.",
            "# TYPE newshash_records_all_total gauge",
            f"newshash_records_all_total {total_records}",
            "# HELP newshash_images_all_total Total number of stored images.",
            "# TYPE newshash_images_all_total gauge",
            f"newshash_images_all_total {total_images}",
            "# HELP newshash_source_errors_all_total Total number of unacknowledged source errors.",
            "# TYPE newshash_source_errors_all_total counter",
            f"newshash_source_errors_all_total {total_errors}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_help(theme: str = "lite", language: str = "de") -> str:
    """Erzeuge die Beschreibungs- und FAQ-Seite der WebUI."""

    language = language if language in {"de", "en"} else "de"
    documentation_name = "description_for_enduser_en.md" if language == "en" else "description_for_enduser.md"
    documentation_path = next(
        (
            parent / "project-docu" / documentation_name
            for parent in Path(__file__).resolve().parents
            if (parent / "project-docu" / documentation_name).is_file()
        ),
        None,
    )
    if documentation_path is None:
        raise FileNotFoundError(f"Could not find project documentation: project-docu/{documentation_name}")
    documentation = markdown.markdown(documentation_path.read_text(encoding="utf-8"), extensions=["extra"])
    other_language = "en" if language == "de" else "de"
    language_label = "English" if language == "de" else "Deutsch"
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="/favicon.svg?v=1&amp;theme={theme}" type="image/svg+xml" sizes="any">
<title>News-Hash</title><style>
  :root {{ --bg:#f5f7fa; --panel:#fff; --line:#cbd2da; --text:#20252b; --muted:#68727d; --accent:#2463a5 }}
  body.theme-dark {{ --bg:#000; --panel:#292826; --line:#f1eadc; --text:#f1eadc; --muted:#b9b1a2; --accent:#ffb000; color-scheme:dark }}
  body.theme-comic {{ --bg:#4b8ed8; --panel:#fffdf5; --line:#171717; --text:#171717; --muted:#5a5145; --accent:#ef4b3f; color-scheme:light }}
  body.theme-paper {{ --bg:#e5d5b8; --panel:#fff9eb; --line:#3a2a20; --text:#2b201b; --muted:#756153; --accent:#b83b32; color-scheme:light }}
  body.theme-news {{ --bg:#f1f2f0; --panel:#fff; --line:#151515; --text:#151515; --muted:#687078; --accent:#d71920; color-scheme:light }}
  * {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.6 system-ui,sans-serif }}
  main {{ max-width:900px; margin:auto; padding:40px 20px }} a {{ color:var(--accent) }}
  .back {{ display:inline-block; margin-bottom:30px }} h1 {{ font:700 48px/1.1 Georgia,serif; margin:0 0 12px }}
  .language-switch {{ float:right; border:1px solid var(--line); padding:5px 9px; text-decoration:none }}
  h2 {{ border-bottom:1px solid var(--line); margin-top:42px; padding-bottom:8px }} h3 {{ margin-top:28px }}
  p, li {{ color:var(--muted) }} code {{ background:var(--panel); border:1px solid var(--line); padding:2px 5px }}
  pre {{ background:var(--panel); border:1px solid var(--line); overflow:auto; padding:14px }}
  .markdown {{ background:var(--panel); border:1px solid var(--line); padding:20px 24px }}
  .markdown a {{ color:var(--accent) }}
  body.theme-comic .markdown {{ border:4px solid var(--line); box-shadow:6px 6px 0 var(--accent) }}
  body.theme-paper h1, body.theme-dark h1 {{ font-family:Georgia,serif }}
</style></head><body class="theme-{theme}"><main>
  <a class="language-switch" href="/hilfe?theme={theme}&amp;lang={other_language}">{language_label}</a>
  <a class="back" href="/?theme={theme}">Zurück zum Dashboard</a>
  <article class="markdown">{documentation}</article>
</main></body></html>"""


def render_detail(
    record: dict[str, Any],
    source_name: str,
    theme: str = "lite",
    storage_name: str = "",
    previous_record: dict[str, str] | None = None,
    next_record: dict[str, str] | None = None,
) -> str:
    """Erzeuge die Detailansicht eines gespeicherten Records."""

    images = "".join(
        f'<a href="{_media_url(storage_name, str(metadata.get("path", "")))}" target="_blank" rel="noreferrer">'
        f'<img src="{_media_url(storage_name, str(metadata.get("path", "")))}" alt="Bild zur Meldung"></a>'
        for metadata in record.get("images", {}).values()
    )
    content_section = f'<article class="content">{record["content"]}</article>' if record.get("content") else ""
    previous_link = (
        f'<a href="{_detail_url({**previous_record, "storage_name": storage_name, "theme": theme})}">← Vorgänger</a>'
        if previous_record
        else '<span class="nav-placeholder"></span>'
    )
    next_link = (
        f'<a href="{_detail_url({**next_record, "storage_name": storage_name, "theme": theme})}">Nachfolger →</a>'
        if next_record
        else '<span class="nav-placeholder"></span>'
    )
    theme_picker = f"""<label class="record-theme"><select onchange="setTheme(this.value)" aria-label="Theme">
      <option value="lite" {"selected" if theme == "lite" else ""}>LightMode</option>
      <option value="dark" {"selected" if theme == "dark" else ""}>DarkMode</option>
      <option value="paper" {"selected" if theme == "paper" else ""}>Papier</option>
      <option value="news" {"selected" if theme == "news" else ""}>News</option>
      <option value="comic" {"selected" if theme == "comic" else ""}>Comic</option>
    </select></label>"""
    navigation = f'<nav class="record-navigation">{previous_link}{theme_picker}{next_link}</nav>' if previous_record or next_record else ""
    back_link = f'<a href="/?source={quote(source_name, safe="")}&amp;page=1&amp;theme={theme}">Zurück zur Quelle</a>'
    top_navigation = f'<nav class="record-navigation top-navigation">{previous_link}{back_link}{next_link}</nav>'
    return f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="icon" href="/favicon.svg?v=1&amp;theme={theme}" type="image/svg+xml" sizes="any">
<link rel="shortcut icon" href="/favicon.svg?v=1&amp;theme={theme}" type="image/svg+xml">
<title>News-Hash</title>
<style>
  :root {{ color-scheme:light; --bg:#4b8ed8; --panel:#fffdf5; --line:#171717; --text:#171717; --muted:#5a5145; --accent:#ef4b3f; --blue:#2c75d6 }}
  body.theme-dark {{ --bg:#000000; --panel:#292826; --line:#f1eadc; --text:#f1eadc; --muted:#b9b1a2; --accent:#ffb000; --blue:#55c5d8; color-scheme:dark }}
  body.theme-lite {{ --bg:#f5f7fa; --panel:#ffffff; --line:#cbd2da; --text:#20252b; --muted:#68727d; --accent:#2463a5; --blue:#4d83b8 }}
  body.theme-paper {{ --bg:#e5d5b8; --panel:#fff9eb; --line:#3a2a20; --text:#2b201b; --muted:#756153; --accent:#b83b32; --blue:#286a9e }}
  * {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg);
    color:var(--text); font:16px/1.65 "Comic Sans MS","Trebuchet MS",sans-serif }}
  main {{ max-width:820px; margin:auto; padding:clamp(24px,5vw,64px) 20px }}
  a {{ color:var(--blue) }}
  .eyebrow {{ color:var(--accent); text-transform:uppercase; letter-spacing:.14em; font-size:12px; font-weight:900; margin-top:42px }}
  h1 {{ color:var(--text); font:900 clamp(20px,3.6vw,36px)/1.05 Impact,"Arial Black",sans-serif;
    letter-spacing:.01em; text-shadow:3px 3px 0 var(--accent); margin:10px 0 16px }}
  .meta-grid {{ color:var(--muted); display:grid; font-size:13px; font-weight:700; gap:8px 24px;
    grid-template-columns:1fr; margin-top:8px }}
  .meta-item {{ overflow-x:auto; white-space:nowrap }}
  .meta-item .local-time {{ color:var(--text); font:11px/1.3 ui-monospace,SFMono-Regular,monospace; white-space:nowrap }}
  .meta-item code {{ color:var(--text); display:inline; font:11px/1.3 ui-monospace,SFMono-Regular,monospace; overflow-x:auto; white-space:nowrap }}
  .content {{ margin-top:34px; background:var(--panel);
    border:4px solid var(--line); box-shadow:8px 8px 0 var(--line); padding:24px; color:var(--text) }}
  .content img {{ max-width:100%; height:auto }} .gallery {{ display:grid;
    grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin-top:32px }}
  .gallery a {{ display:block }}
  .gallery img {{ display:block; height:auto; max-width:100%; width:100%; border:4px solid var(--line); box-shadow:5px 5px 0 var(--blue) }}
  .record-navigation {{ display:flex; gap:16px; margin-top:20px }}
  .record-navigation a, .record-theme {{ background:var(--panel); border:3px solid var(--line); flex:1; min-width:0; padding:5px 10px;
    font-size:clamp(10px,1.7vw,14px); overflow:hidden; text-align:center; text-decoration:none; text-overflow:ellipsis;
    transform:none; white-space:nowrap }}
  .nav-placeholder {{ flex:1 }}
  .record-theme {{ align-items:center; display:flex; justify-content:center;
    min-width:0; padding:4px 8px }}
  .record-theme select {{ background:transparent; border:0; color:var(--text); font:inherit; font-weight:700; max-width:100% }}
  body.theme-dark, body.theme-lite, body.theme-paper, body.theme-news {{ font-family:system-ui,sans-serif }}
  body.theme-dark h1, body.theme-lite h1, body.theme-paper h1, body.theme-news h1 {{ font-family:Georgia,serif; text-shadow:none; letter-spacing:-.04em }}
  body.theme-comic h1 {{ text-shadow:none }}
  body.theme-dark .record-navigation a, body.theme-dark .record-theme,
  body.theme-lite .record-navigation a, body.theme-lite .record-theme,
  body.theme-paper .record-navigation a, body.theme-paper .record-theme,
  body.theme-news .record-navigation a, body.theme-news .record-theme {{ border-width:1px; border-radius:6px; box-shadow:none; transform:none }}
  body.theme-dark .content, body.theme-lite .content, body.theme-paper .content, body.theme-news .content {{
    border-width:1px; border-radius:8px; box-shadow:none }}
  body.theme-dark .gallery img, body.theme-lite .gallery img, body.theme-paper .gallery img,
  body.theme-news .gallery img {{ border-width:1px; border-radius:6px; box-shadow:none }}
  body.theme-paper {{ --bg:#e7e0d0; --panel:#fbf8ef; --line:#39332c; --text:#29251f; --muted:#746b5e; --accent:#9d3029; --blue:#4e5962 }}
  body.theme-news {{ --bg:#f1f2f0; --panel:#fff; --line:#151515; --text:#151515; --muted:#687078; --accent:#d71920; --blue:#003b70 }}
  body.theme-paper main {{ max-width:860px }}
  body.theme-paper h1 {{ font-weight:700; text-transform:uppercase; letter-spacing:.02em }}
  body.theme-paper .content {{ border-radius:0; padding:28px; background:var(--panel) }}
  body.theme-news h1 {{ font-weight:800; text-transform:none }}
  body.theme-news .detail-header {{ border-top:4px solid var(--accent); padding-top:12px }}
  .detail-header {{ margin-top:28px }}
  body.theme-comic .detail-header {{ background:var(--panel); border:4px solid var(--line); box-shadow:6px 6px 0 var(--blue); padding:12px }}
  body.theme-comic .detail-header .eyebrow {{ margin-top:0 }}
  body.theme-comic .detail-header h1 {{ margin:6px 0 10px }}
  body.theme-comic .content {{ box-shadow:8px 8px 0 var(--blue) }}
  @media print {{ .record-navigation, .record-theme {{ display:none !important }}
    body {{ background:white; color:black; zoom:90% }} .content {{ box-shadow:none }} }}
</style></head><body class="theme-{theme}"><main>
  {top_navigation}
  <div class="detail-header">
  <div class="eyebrow">{_text(source_name)}</div>
  <h1>{_text(record.get("title"))}</h1>
  <div class="meta-grid">
    <div class="meta-item">Veröffentlicht: {_local_time(record.get("published_at"))}</div>
    <div class="meta-item">Importiert: {_local_time(record.get("retrieved_at"))}</div>
    <div class="meta-item">Hash: <code>{_text(record.get("hash"))}</code></div>
    <div class="meta-item">PreHash: <code>{_text(record.get("previous_hash"))}</code></div>
  </div>
  </div>
  {content_section}
  {f'<div class="gallery">{images}</div>' if images else ""}
  {navigation}
  <script>
    function setTheme(theme) {{
      const params = new URLSearchParams(location.search);
      params.set("theme", theme);
      location.search = params;
    }}
    document.querySelectorAll(".local-time").forEach((element) => {{
      const date = new Date(element.dateTime);
      if (!Number.isNaN(date.valueOf())) {{
        element.textContent = new Intl.DateTimeFormat("de-DE", {{
          dateStyle: "medium", timeStyle: "short"
        }}).format(date);
      }}
    }});
  </script>
</main></body></html>"""


def render_dashboard(data: dict[str, Any]) -> str:
    """Erzeuge die responsive HTML-Übersicht für das Dashboard."""

    selected_source = data.get("selected_source")
    page = data.get("page", 1)
    total_pages = data.get("total_pages", 1)
    theme = data.get("theme", "lite")
    theme_query = {"theme": theme}
    page_size_query = {"page_size": data.get("page_size", 10)}
    source_cards = "".join(
        f"""
        <div class="source-card" data-source="{_text(source.name)}">
          <div class="source-top"><span>{_text(source.name)}</span></div>
          <a class="source-count" href="?{_query({"source": source.storage_name, "page": 1, **theme_query})}">
            <strong>{_number(source.records)}</strong><span class="muted"> Meldungen</span>
          </a>
           <div class="source-meta">{_number(source.images)} Bilder · {_number(source.errors)} Fehler<br>
             SQLite: {_data_size(source.sqlite_size_bytes)}<br>
             zuletzt {_local_time(source.latest_retrieved_at)}<br>
            <span class="source-hash">Hash: {_text(source.latest_hash)}</span><br>
            <span class="anchor-status anchor-{source.anchor_status}" title="{_text(source.anchor_status)}">
              {_anchor_label(source.anchor_status)}
            </span>{_anchor_links(source)}</div>
           {_source_error_markup(source, theme_query)}
          <form method="post" action="/fetch?{_query({"source": source.storage_name, **theme_query})}">
            <button class="fetch-button" type="submit">Jetzt abrufen</button>
          </form>
        </div>
        """
        for source in data["sources"]
    )
    record_rows = (
        "".join(
            f"""
        <li data-source="{_text(record.get("source_name"))}">
          <div><span class="eyebrow">{_text(record.get("source_name"))}</span>
          <a href="{_detail_url({**record, "theme": theme})}">{_text(record.get("title"))}</a>
          <div class="record-hash">Hash: {_text(record.get("hash"))}</div></div>
          {_local_time(record.get("published_at") or record.get("retrieved_at"))}
        </li>
        """
            for record in data["records"]
        )
        or '<li class="empty">Noch keine Meldungen importiert.</li>'
    )
    pagination = ""
    pagination_anchor = "#neueste-meldungen"
    if total_pages > 1:
        pagination = '<nav class="pagination" aria-label="Seitennavigation">'
        if page > 1:
            first_query = (
                {"source": selected_source, "page": 1, **page_size_query, **theme_query} if selected_source else {"page": 1, **page_size_query, **theme_query}
            )
            pagination += f'<a href="?{_query(first_query)}{pagination_anchor}">&lt;&lt; Erste</a>'
            previous_query = (
                {"source": selected_source, "page": page - 1, **page_size_query, **theme_query}
                if selected_source
                else {"page": page - 1, **page_size_query, **theme_query}
            )
            pagination += f'<a href="?{_query(previous_query)}{pagination_anchor}">&lt; Zurück</a>'
        pagination += f"<span>Seite {page} von {total_pages}</span>"
        if page < total_pages:
            next_query = (
                {"source": selected_source, "page": page + 1, **page_size_query, **theme_query}
                if selected_source
                else {"page": page + 1, **page_size_query, **theme_query}
            )
            pagination += f'<a href="?{_query(next_query)}{pagination_anchor}">Weiter &gt;</a>'
            last_query = (
                {"source": selected_source, "page": total_pages, **page_size_query, **theme_query}
                if selected_source
                else {"page": total_pages, **page_size_query, **theme_query}
            )
            pagination += f'<a href="?{_query(last_query)}{pagination_anchor}">Letzte &gt;&gt;</a>'
        pagination += (
            '<label class="page-size">Meldungen: <select onchange="changePageSize(this.value)" aria-label="Meldungen pro Seite">'
            + "".join(f'<option value="{size}"{" selected" if size == data.get("page_size", 10) else ""}>{size}</option>' for size in PAGE_SIZES)
            + "</select></label></nav>"
        )

    heading = f"Meldungen · {_text(selected_source)}" if selected_source else "Neueste Meldungen"
    log_entries = "".join(_runtime_log_markup(entry) for entry in reversed(data.get("runtime_logs", [])[-30:]))

    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <link rel="icon" href="/favicon.svg?v=1&amp;theme={theme}" type="image/svg+xml" sizes="any">
  <link rel="shortcut icon" href="/favicon.svg?v=1&amp;theme={theme}" type="image/svg+xml">
  <meta http-equiv="refresh" content="60">
  <title>News-Hash</title>
  <style>
    :root {{ color-scheme:light; --bg:#4b8ed8; --panel:#fffdf5; --line:#171717; --text:#171717; --muted:#5a5145;
      --accent:#ef4b3f; --blue:#2c75d6; --yellow:#f7c936; }}
    body.theme-dark {{ --bg:#000000; --panel:#292826; --line:#f1eadc; --text:#f1eadc; --muted:#b9b1a2;
      --accent:#ffb000; --blue:#55c5d8; color-scheme:dark }}
    body.theme-lite {{ --bg:#f5f7fa; --panel:#ffffff; --line:#cbd2da; --text:#20252b; --muted:#68727d; --accent:#2463a5; --blue:#4d83b8 }}
    body.theme-paper {{ --bg:#e5d5b8; --panel:#fff9eb; --line:#3a2a20; --text:#2b201b; --muted:#756153; --accent:#b83b32; --blue:#286a9e }}
    body.theme-news {{ --bg:#f1f2f0; --panel:#fff; --line:#151515; --text:#151515; --muted:#687078; --accent:#d71920; --blue:#003b70 }}
    * {{ box-sizing:border-box }} body {{ margin:0; background:var(--bg);
      color:var(--text); font:15px/1.5 "Comic Sans MS","Trebuchet MS",sans-serif }}
    main {{ max-width:1120px; margin:auto; padding:clamp(24px,5vw,64px) 20px }}
    header {{ display:flex; justify-content:space-between; gap:20px; align-items:end; margin-bottom:42px }}
    .brand {{ align-items:center; display:flex }} .brand h1 {{ align-items:center; display:flex; gap:14px }} .brand-logo {{ height:48px; width:48px }}
    h1 {{ color:var(--text); font:900 clamp(22px,4.2vw,43px)/.95 Impact,"Arial Black",sans-serif;
      letter-spacing:.01em; text-shadow:4px 4px 0 var(--accent); margin:8px 0 }}
    .kicker,.eyebrow {{ color:var(--accent); text-transform:uppercase; letter-spacing:.14em; font-size:11px; font-weight:900 }}
    .updated {{ color:var(--muted); font-size:13px; text-align:right }}
    .refresh-line {{ align-items:center; display:inline-flex; gap:6px }}
    .refresh-countdown {{ --progress:100%; background:conic-gradient(var(--line) 0 calc(100% - var(--progress)),var(--accent) 0);
      border:0; border-radius:50%; cursor:pointer; height:24px; mask:radial-gradient(farthest-side,#0000 calc(100% - 5px),#000 calc(100% - 4px));
      padding:0; width:24px; -webkit-mask:radial-gradient(farthest-side,#0000 calc(100% - 5px),#000 calc(100% - 4px)) }}
    .theme-picker {{ display:inline-block; margin-left:14px; color:var(--text); font-weight:900 }}
    .theme-picker select {{ margin-left:6px; border:3px solid var(--line); background:var(--panel); color:var(--text);
      padding:4px; font:inherit; font-weight:700 }}
    .metrics {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin-bottom:40px }}
    .metric {{ background:var(--panel); border:4px solid var(--line); box-shadow:6px 6px 0 var(--line); padding:22px; transform:rotate(-1deg) }}
    .metric:nth-child(2) {{ transform:rotate(1deg); background:#d9edff }} .metric:nth-child(3) {{ background:#ffe0dd }}
    .metric strong {{ display:block; font:900 40px/1 Impact,"Arial Black",sans-serif; margin-top:8px }}
    body.theme-lite .metric, body.theme-lite .metric:nth-child(2), body.theme-lite .metric:nth-child(3) {{ background:#d9edff }}
    body.theme-dark .metric, body.theme-dark .metric:nth-child(2), body.theme-dark .metric:nth-child(3) {{ background:var(--panel) }}
    section {{ margin-top:38px }} h2 {{ font:600 25px Georgia,serif; margin:0 0 14px }}
    .sources {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px }}
    .section-heading {{ display:flex; justify-content:space-between; align-items:baseline; gap:16px }}
    .section-heading a, .pagination a {{ display:inline-block; color:var(--text); background:var(--panel); border:3px solid var(--line);
      box-shadow:3px 3px 0 var(--line); padding:5px 9px; font-size:13px; font-weight:900; text-decoration:none }}
    .section-heading a:hover, .pagination a:hover {{ transform:translate(2px,2px); box-shadow:1px 1px 0 var(--line) }}
    .source-card {{ display:block; color:inherit; text-decoration:none; background:var(--panel); border:4px solid var(--line);
      box-shadow:5px 5px 0 var(--blue); padding:18px; transform:rotate(-.6deg) }}
    .source-card:nth-child(even) {{ transform:rotate(.6deg); box-shadow:5px 5px 0 var(--accent) }}
    .source-card:nth-child(3n) {{ box-shadow:5px 5px 0 #7b61ff }}
    .source-card:nth-child(4n) {{ box-shadow:5px 5px 0 #35b87f }}
    body.theme-comic .metric:nth-child(1) {{ box-shadow:6px 6px 0 var(--blue) }}
    body.theme-comic .metric:nth-child(2) {{ box-shadow:6px 6px 0 var(--accent) }}
    body.theme-comic .metric:nth-child(3) {{ box-shadow:6px 6px 0 #7b61ff }}
    body.theme-comic h1 {{ background:var(--panel); border:4px solid var(--line); box-shadow:6px 6px 0 var(--accent);
      display:flex; padding:10px 16px; text-shadow:none }}
    body.theme-comic .latest li:nth-child(4n+1) {{ box-shadow:4px 4px 0 var(--blue) }}
    body.theme-comic .latest li:nth-child(4n+2) {{ box-shadow:4px 4px 0 var(--accent) }}
    body.theme-comic .latest li:nth-child(4n+3) {{ box-shadow:4px 4px 0 #7b61ff }}
    body.theme-comic .latest li:nth-child(4n) {{ box-shadow:4px 4px 0 #35b87f }}
    .source-card:hover {{ transform:translateY(-4px) rotate(-.6deg) }}
    .source-top {{ display:flex; gap:8px; align-items:center; margin-bottom:20px; color:var(--muted) }}
    .dot {{ width:12px; height:12px; background:var(--accent); border:2px solid var(--line); border-radius:50% }}
    .source-card strong {{ font:900 31px Impact,"Arial Black",sans-serif }}
    .muted,.source-meta {{ color:var(--muted) }} .source-meta {{ margin-top:16px; font-size:12px }}
    .source-error {{ color:var(--accent); font-size:12px; font-weight:700; margin-top:10px; overflow-wrap:anywhere }}
    .source-hash {{ display:inline-block; font:11px/1.3 ui-monospace,SFMono-Regular,monospace; overflow-wrap:anywhere }}
    .anchor-status {{ display:inline-flex; align-items:center; gap:4px; font-weight:900 }}
    .anchor-complete {{ color:#18834b }} .anchor-pending {{ color:#a56b00 }}
    .anchor-no_anchor, .anchor-no_ots {{ color:var(--muted) }}
    .anchor-files {{ display:inline-block; white-space:nowrap }}
    .source-count {{ display:inline-block; color:inherit; text-decoration:none }}
    .source-count:hover strong {{ color:var(--accent) }}
     .fetch-button {{ margin-top:16px; border:3px solid var(--line); background:var(--blue); color:white; box-shadow:3px 3px 0 var(--line);
       cursor:pointer; padding:6px 10px; font:900 12px "Comic Sans MS",sans-serif }}
     .fetch-button:hover {{ transform:translate(2px,2px); box-shadow:1px 1px 0 var(--line) }}
     .acknowledge-button {{ margin-top:8px; border:2px solid var(--line); background:var(--panel); color:var(--line); cursor:pointer; padding:4px 8px;
       font:700 11px "Comic Sans MS",sans-serif }}
     .acknowledge-button:hover {{ background:var(--paper); transform:translate(1px,1px) }}
     .runtime-log {{ background:var(--panel); border:3px solid var(--line); box-shadow:4px 4px 0 var(--line); padding:14px 18px; margin-top:38px }}
    body.theme-comic .runtime-log {{ box-shadow:5px 5px 0 #f7c936 }}
    .runtime-log h2 {{ margin-top:0 }} .runtime-log ul {{ list-style:none; padding:0; margin:0; max-height:260px; overflow:auto }}
    .runtime-log li {{ border-bottom:1px solid var(--line); color:var(--muted); font:12px/1.5 ui-monospace,SFMono-Regular,monospace; padding:6px 0 }}
    .latest {{ list-style:none; padding:0; margin:0; border-top:1px solid var(--line) }}
    .latest li {{ display:flex; justify-content:space-between; gap:18px; padding:16px 18px; margin:10px 0; background:var(--panel);
      border:3px solid var(--line); box-shadow:4px 4px 0 var(--line) }}
    .latest a {{ display:block; color:var(--blue); font-weight:900; text-decoration:none; margin-top:3px }}
    .latest a:hover {{ color:var(--accent) }} time {{ color:var(--muted); white-space:nowrap; font-size:12px }}
    .record-hash {{ color:var(--muted); font:11px/1.3 ui-monospace,SFMono-Regular,monospace; margin-top:6px; overflow-wrap:anywhere }}
    .empty {{ color:var(--muted) }}
     .pagination {{ display:flex; justify-content:center; align-items:center; gap:20px; margin-top:20px; color:var(--muted); flex-wrap:wrap }}
     .page-size {{ display:inline-flex; align-items:center; gap:6px }}
     .page-size select {{ border:2px solid var(--line); padding:4px; background:var(--panel); color:var(--text) }}
    .shutdown {{ margin-top:42px; border:3px solid var(--line); background:var(--accent); color:white; box-shadow:3px 3px 0 var(--line);
      cursor:pointer; padding:6px 10px; font:900 12px "Comic Sans MS",sans-serif }}
    .shutdown:hover {{ transform:translate(2px,2px); box-shadow:2px 2px 0 var(--line) }}
    .footer-actions {{ align-items:center; display:flex; flex-wrap:wrap; gap:12px; margin-top:24px }}
    .footer-actions .shutdown {{ margin-top:0 }}
    .site-footer {{ color:var(--muted); font-size:12px; letter-spacing:.04em; margin-top:34px; text-align:center }}
    .site-footer .spark {{ color:var(--accent); font-size:16px; vertical-align:-1px }}
    .help-link {{ color:var(--accent); font-weight:900; text-decoration:none }}
    body.theme-dark, body.theme-lite, body.theme-paper, body.theme-news {{ font-family:system-ui,sans-serif }}
    body.theme-dark h1, body.theme-lite h1, body.theme-paper h1, body.theme-news h1 {{ font-family:Georgia,serif; text-shadow:none; letter-spacing:-.04em }}
    body.theme-dark .metric, body.theme-lite .metric, body.theme-paper .metric,
    body.theme-dark .source-card, body.theme-lite .source-card, body.theme-paper .source-card, body.theme-news .source-card {{ border-width:1px;
      border-radius:8px; box-shadow:none; transform:none }}
    body.theme-paper .source-card:hover {{ transform:translateY(-2px) }}
    body.theme-dark .latest li, body.theme-lite .latest li, body.theme-paper .latest li,
    body.theme-news .latest li {{ border-width:1px; border-radius:8px; box-shadow:none }}
    body.theme-dark .shutdown, body.theme-lite .shutdown, body.theme-paper .shutdown, body.theme-news .shutdown {{ border-width:1px;
      border-radius:6px; box-shadow:none; font-family:system-ui,sans-serif }}
    body.theme-dark .fetch-button, body.theme-lite .fetch-button, body.theme-paper .fetch-button, body.theme-news .fetch-button {{ border-width:1px;
      border-radius:5px; box-shadow:none; font-family:system-ui,sans-serif }}
    body.theme-dark .section-heading a, body.theme-dark .pagination a, body.theme-dark .fetch-button,
    body.theme-dark .shutdown, body.theme-dark .theme-picker select,
    body.theme-lite .section-heading a, body.theme-lite .pagination a, body.theme-lite .fetch-button,
    body.theme-lite .shutdown, body.theme-lite .theme-picker select {{ border:1px solid var(--line); border-radius:5px; box-shadow:none }}
    body.theme-news .section-heading a, body.theme-news .pagination a, body.theme-news .fetch-button,
    body.theme-news .shutdown, body.theme-news .theme-picker select {{ border:1px solid var(--line); border-radius:5px; box-shadow:none }}
    body.theme-dark .shutdown {{ background:#ef4b3f; color:white }}
    body.theme-lite .shutdown {{ background:#ef4b3f; color:white }}
    body.theme-dark .refresh-countdown {{ background:conic-gradient(#000 0 calc(100% - var(--progress)),var(--accent) 0) }}
    body.theme-paper header {{ border-bottom:4px double var(--line); padding-bottom:18px; margin-bottom:34px }}
    body.theme-paper h1 {{ font-weight:700; text-transform:uppercase; letter-spacing:.02em }}
    body.theme-paper .metrics {{ gap:0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); padding:12px 0 }}
    body.theme-paper .metric {{ border:0; border-right:1px solid var(--line); border-radius:0; background:transparent; box-shadow:none; transform:none }}
    body.theme-paper .metric:last-child {{ border-right:0 }}
    body.theme-paper .source-card {{ border:1px solid #aaa39a; border-radius:0; background:transparent; box-shadow:none; transform:none }}
    body.theme-paper .source-card:nth-child(even) {{ transform:none; box-shadow:none }}
    body.theme-paper .source-card:hover {{ transform:none; background:var(--panel) }}
    body.theme-paper .section-heading {{ border-top:3px solid var(--line); border-bottom:1px solid var(--line); padding:8px 0 }}
    body.theme-paper .section-heading {{ align-items:center }}
    body.theme-paper .section-heading h2 {{ margin:0 }}
    body.theme-paper .latest li {{ border-width:0 0 1px; border-radius:0; background:transparent; box-shadow:none; margin:0; padding:14px 0 }}
    body.theme-paper .latest a {{ color:var(--text); font-family:Georgia,serif; font-size:17px }}
    @media print {{ button, form, .runtime-log, .theme-picker, .pagination, .section-heading a, .anchor-files {{ display:none !important }}
      body {{ background:white; color:black; zoom:90% }} .source-card, .metric, .latest li {{ box-shadow:none; break-inside:avoid }} }}
  </style>
</head>
<body class="theme-{theme}"><main>
  <header><div class="brand"><h1><img class="brand-logo" src="/logo.svg?theme={theme}" alt="News-Hash">News-Hash</h1></div>
    <div class="updated"><a class="help-link" href="/hilfe?theme={theme}">Hilfe &amp; FAQ</a><br><span class="refresh-line">Live-Übersicht
      <button class="refresh-countdown" id="refresh-countdown" type="button"
        title="Nächste Aktualisierung in 60 Sekunden" aria-label="Seite sofort aktualisieren"></button></span><br>
      Stand {_local_time(data["generated_at"])}<br>
      </div></header>
  <div class="metrics">
    <div class="metric"><span class="kicker">Quellen</span><strong>{len(data["sources"])}</strong></div>
    <div class="metric"><span class="kicker">Meldungen</span><strong>{_number(data["total_records"])}</strong></div>
    <div class="metric"><span class="kicker">Bilder</span><strong>{_number(data["total_images"])}</strong></div>
  </div>
  <section><h2>Quellen</h2><div class="sources">{source_cards}</div></section>
  <section id="neueste-meldungen"><div class="section-heading"><h2>{heading}</h2>
    <a href="?{_query({"page": 1, **theme_query})}">Filter zurücksetzen</a></div>
    <ul class="latest">{record_rows}</ul>{pagination}</section>
  <section class="runtime-log"><h2>Laufzeit-Log</h2><ul>{log_entries or "<li>Noch keine Laufzeitereignisse.</li>"}</ul></section>
  <div class="footer-actions"><button class="shutdown" type="button" onclick="shutdownDaemon()">Daemon beenden</button>
    <label class="theme-picker"><select onchange="setTheme(this.value)">
      <option value="lite" {"selected" if theme == "lite" else ""}>LightMode</option>
      <option value="dark" {"selected" if theme == "dark" else ""}>DarkMode</option>
      <option value="paper" {"selected" if theme == "paper" else ""}>Papier</option>
      <option value="news" {"selected" if theme == "news" else ""}>News</option>
      <option value="comic" {"selected" if theme == "comic" else ""}>Comic</option>
    </select></label></div>
  <footer class="site-footer"><span class="spark">✦</span> Mit KI gebaut, mit Liebe verfeinert, für neugierige Menschen <span class="spark">♥</span><br>
    Entwickelt mit <a href="https://opencode.ai/" target="_blank" rel="noreferrer">OpenCode</a> ·
    <a href="https://www.y-o-b.de/" target="_blank" rel="noreferrer">www.y-o-b.de</a><br>
    <a class="verification-link" href="https://opentimestamps.org/" target="_blank" rel="noreferrer">OpenTimestamps-Proof online verifizieren</a></footer>
  <script>
    if (document.body.classList.contains("theme-comic")) {{
      const comicColors = ["#2c75d6", "#ef4b3f", "#7b61ff", "#35b87f", "#f7c936"];
      const sourceColors = ["#2c75d6", "#ef4b3f", "#7b61ff", "#35b87f", "#f7c936", "#e26d9b", "#00a6a6"];
      const sourceColorMap = new Map();
      document.querySelectorAll(".source-card").forEach((element, index) => {{
        const source = element.dataset.source;
        const color = sourceColors[index % sourceColors.length];
        sourceColorMap.set(source, color);
        element.style.boxShadow = `5px 5px 0 ${{color}}`;
      }});
      document.querySelectorAll(".latest li").forEach((element) => {{
        const color = sourceColorMap.get(element.dataset.source);
        if (color) element.style.boxShadow = `4px 4px 0 ${{color}}`;
      }});
      const shadowTargets = [
        [".metric", "6px 6px 0"], [".runtime-log", "5px 5px 0"], [".brand h1", "6px 6px 0"]
      ];
      shadowTargets.forEach(([selector, size]) => document.querySelectorAll(selector).forEach((element) => {{
        const color = comicColors[Math.floor(Math.random() * comicColors.length)];
        element.style.boxShadow = `${{size}} ${{color}}`;
      }}));
    }}
    const refreshCountdown = document.getElementById("refresh-countdown");
    let secondsUntilRefresh = 60;
    const resetCountdown = () => {{
      secondsUntilRefresh = 60;
      refreshCountdown.style.setProperty("--progress", "100%");
      refreshCountdown.title = "Nächste Aktualisierung in 60 Sekunden";
    }};
    refreshCountdown.addEventListener("click", () => {{
      resetCountdown();
      location.reload();
    }});
    setInterval(() => {{
      secondsUntilRefresh -= 1;
      if (secondsUntilRefresh <= 0) {{
        resetCountdown();
        location.reload();
        return;
      }}
      refreshCountdown.style.setProperty("--progress", `${{secondsUntilRefresh / 60 * 100}}%`);
      refreshCountdown.title = `Nächste Aktualisierung in ${{secondsUntilRefresh}} Sekunden`;
    }}, 1000);
    function setTheme(theme) {{
      const params = new URLSearchParams(location.search);
      params.set("theme", theme);
      params.set("page", "1");
      location.search = params;
    }}
    document.querySelectorAll(".local-time").forEach((element) => {{
      const date = new Date(element.dateTime);
      if (!Number.isNaN(date.valueOf())) {{
        const timeStyle = element.classList.contains("log-time") ? "medium" : "short";
        element.textContent = new Intl.DateTimeFormat("de-DE", {{
          dateStyle: "medium", timeStyle
        }}).format(date);
      }}
    }});
     async function shutdownDaemon() {{
      if (!confirm("Daemon wirklich beenden?")) return;
      await fetch("/shutdown", {{ method: "POST" }});
      document.querySelector(".shutdown").textContent = "Daemon wird beendet ...";
     }}
     function changePageSize(value) {{
       const params = new URLSearchParams(location.search);
       params.set("page", "1");
       params.set("page_size", value);
       location.hash = "neueste-meldungen";
       location.search = params;
     }}
  </script>
</main></body></html>"""


def run_web_server(
    config: AppConfig,
    settings_manager: SettingsManager,
    host: str,
    port: int,
    stop_event: threading.Event | None = None,
) -> None:
    """Starte den kleinen HTTP-Server für das Dashboard."""

    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed_path = urlparse(self.path)
            if parsed_path.path in {"/favicon.svg", "/logo.svg"}:
                logo = LOGO_PAPER_SVG if parse_qs(parsed_path.query).get("theme", [""])[0] == "paper" else LOGO_SVG
                self._send_body(logo.encode("utf-8"), "image/svg+xml")
                return
            if parsed_path.path == "/metrics":
                body = render_metrics(config, settings_manager).encode("utf-8")
                self._send_body(body, "text/plain; version=0.0.4; charset=utf-8")
                return
            if parsed_path.path == "/hilfe":
                query = parse_qs(parsed_path.query)
                theme = query.get("theme", ["lite"])[0]
                if theme not in THEMES:
                    theme = "lite"
                language = query.get("lang", ["de"])[0]
                self._send_body(render_help(theme, language).encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed_path.path.startswith("/anchor/"):
                parts = parsed_path.path.split("/")
                if len(parts) != 5 or parts[4] not in {"manifest", "proof"}:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                storage_name, day_text, kind = unquote(parts[2]), unquote(parts[3]), parts[4]
                source = next((item for item in config.settings.sources if item.storage_name == storage_name), None)
                try:
                    anchor_day = date.fromisoformat(day_text)
                except ValueError:
                    anchor_day = None
                if source is None or anchor_day is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                anchor = OpenTimestampsAnchor(settings_manager.storage_root())
                file_path = anchor.manifest_path(source, anchor_day) if kind == "manifest" else anchor.proof_path(source, anchor_day)
                if not file_path.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                content_type = "text/plain; charset=utf-8" if kind == "manifest" else "application/octet-stream"
                self._send_body(file_path.read_bytes(), content_type, f'attachment; filename="{file_path.name}"')
                return
            if parsed_path.path.startswith("/meldung/"):
                parts = parsed_path.path.split("/")
                if len(parts) != 4:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                storage_name, source_id = unquote(parts[2]), unquote(parts[3])
                source = next((item for item in config.settings.sources if item.storage_name == storage_name), None)
                record = SqliteStorage(settings_manager.storage_root(), storage_name).get_record(source_id) if source else None
                if source is None or record is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                detail_theme = parse_qs(parsed_path.query).get("theme", ["lite"])[0]
                if detail_theme not in THEMES:
                    detail_theme = "lite"
                previous_record, next_record = SqliteStorage(settings_manager.storage_root(), storage_name).adjacent_records(source_id)
                body = render_detail(record, source.name, detail_theme, storage_name, previous_record, next_record).encode("utf-8")
                self._send_body(body, "text/html; charset=utf-8")
                return
            if parsed_path.path.startswith("/media/"):
                media_parts = parsed_path.path.removeprefix("/media/").split("/", 1)
                if len(media_parts) != 2:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                storage_name, relative_path = unquote(media_parts[0]), unquote(media_parts[1])
                if not any(source.storage_name == storage_name for source in config.settings.sources):
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                root = (settings_manager.storage_root() / storage_name).resolve()
                media_path = (root / relative_path).resolve()
                if not media_path.is_relative_to(root) or not media_path.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                self._send_body(media_path.read_bytes(), mimetypes.guess_type(media_path.name)[0] or "application/octet-stream")
                return
            if parsed_path.path not in {"/", "/index.html"}:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            query = parse_qs(parsed_path.query)
            selected_source = query.get("source", [None])[0]
            theme = query.get("theme", ["lite"])[0]
            if theme not in THEMES:
                theme = "lite"
            try:
                page = int(query.get("page", ["1"])[0])
            except ValueError:
                page = 1
            try:
                page_size = int(query.get("page_size", ["10"])[0])
            except ValueError:
                page_size = 10
            if page_size not in PAGE_SIZES:
                page_size = 10
            dashboard_data = collect_dashboard_data(config, settings_manager, selected_source, page, page_size)
            dashboard_data["theme"] = theme
            body = render_dashboard(dashboard_data).encode("utf-8")
            self._send_body(body, "text/html; charset=utf-8")

        def _send_body(self, body: bytes, content_type: str, content_disposition: str | None = None) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            if content_disposition:
                self.send_header("Content-Disposition", content_disposition)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            parsed_path = urlparse(self.path)
            if parsed_path.path == "/fetch":
                query = parse_qs(parsed_path.query)
                storage_name = query.get("source", [""])[0]
                source = next((item for item in config.settings.sources if item.storage_name == storage_name), None)
                if source is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                try:
                    from newshash.main import ingest_source

                    ingest_source(source, settings_manager)
                except Exception:
                    pass
                theme = query.get("theme", ["lite"])[0]
                if theme not in THEMES:
                    theme = "lite"
                location = "/?" + urlencode({"source": source.storage_name, "page": 1, "theme": theme})
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", location)
                self.end_headers()
                return
            if parsed_path.path == "/acknowledge-error":
                query = parse_qs(parsed_path.query)
                storage_name = query.get("source", [""])[0]
                source = next((item for item in config.settings.sources if item.storage_name == storage_name), None)
                if source is None:
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                settings_manager.acknowledge_source_errors(source.name)
                theme = query.get("theme", ["lite"])[0]
                if theme not in THEMES:
                    theme = "lite"
                location = "/?" + urlencode({"source": source.storage_name, "page": 1, "theme": theme})
                self.send_response(HTTPStatus.SEE_OTHER)
                self.send_header("Location", location)
                self.end_headers()
                return
            if urlparse(self.path).path != "/shutdown" or stop_event is None:
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            stop_event.set()
            body = b"Daemon wird beendet."
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            threading.Thread(target=server.shutdown, name="newshash-web-shutdown", daemon=True).start()

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), DashboardHandler)
    print(f"web=listening http://{host}:{server.server_port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("web=stopped")
    finally:
        server.server_close()
