from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from mimetypes import guess_extension
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree

import requests

from newshash.metadata import metadata_hashes

GENESIS_HASH = "0" * 64
REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = "newshash/0.1"


class _ImgTagParser(HTMLParser):
    """Sammle die src-Attribute aller <img>-Tags in einem HTML-Fragment."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Merke die Bild-URL, sobald ein <img>-Tag mit src erkannt wird."""

        if tag != "img":
            return

        for attr_name, attr_value in attrs:
            if attr_name == "src" and attr_value:
                self.urls.append(attr_value)
                break


class RSSv0:
    """Codec fuer RSSv0-basierte Records, Bild-Verarbeitung und Hash-Bildung."""

    codec_name = "RSSv0"

    def utc_now(self) -> str:
        """Gib die aktuelle UTC-Zeit als ISO-String zurueck."""

        return datetime.now(UTC).isoformat()

    def fetch_feed(self, url: str) -> dict[str, Any]:
        """Lade einen JSON- oder klassischen XML-RSS-Feed per HTTP."""

        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        if "json" in response.headers.get("Content-Type", "").lower():
            return response.json()
        return self._parse_xml_feed(response.content)

    def normalize_timestamp(self, value: Any) -> str:
        """Normalisiere ISO- und RFC-822-Zeitstempel nach UTC-ISO."""

        text = str(value or "")
        if not text:
            return ""
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = parsedate_to_datetime(text)
            except (TypeError, ValueError, OverflowError):
                return text
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")

    def _parse_xml_feed(self, content: bytes) -> dict[str, Any]:
        """Normalisiere einen RSS-2.0-Feed auf das interne Feed-Format."""

        root = ElementTree.fromstring(content)

        def child_text(element: ElementTree.Element, name: str) -> str:
            child = next((candidate for candidate in element if candidate.tag.rsplit("}", 1)[-1] == name), None)
            return (child.text or "").strip() if child is not None else ""

        def iso_date(value: str) -> str:
            return self.normalize_timestamp(value)

        items: list[dict[str, Any]] = []
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] != "item":
                continue
            link = child_text(element, "link")
            guid = child_text(element, "guid") or link
            description = child_text(element, "description")
            enclosure = next((candidate for candidate in element if candidate.tag.rsplit("}", 1)[-1] == "enclosure"), None)
            image_url = enclosure.get("url", "") if enclosure is not None else ""
            content_html = description
            if image_url:
                content_html += f'<img src="{image_url}">'
            pub_date = iso_date(child_text(element, "pubDate"))
            items.append(
                {
                    "id": guid,
                    "title": child_text(element, "title"),
                    "url": link,
                    "content_html": content_html,
                    "date_modified": pub_date,
                    "_rssbridge": {"link": link, "guid": guid, "pubDate": pub_date},
                }
            )
        return {"items": items}

    def fetch_image(self, url: str) -> tuple[bytes, str | None]:
        """Lade ein Bild per HTTP und gib Rohbytes sowie Content-Type zurueck."""

        response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.content, response.headers.get("Content-Type")

    def canonical_json(self, value: Any) -> str:
        """Serialisiere Werte kanonisch fuer stabile Hashes."""

        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def digest_record(self, data: dict[str, Any]) -> str:
        """Bilde den SHA256-Hash ueber kanonische JSON-Daten."""

        return hashlib.sha256(self.canonical_json(data).encode("utf-8")).hexdigest()

    def record_hash_material(self, record: dict[str, Any], previous_hash: str) -> dict[str, Any]:
        """Extrahiere das Material, das in den Hash eingeht."""

        return {
            "author_name": record.get("author_name"),
            "content": record.get("content"),
            "codec_name": record.get("codec_name"),
            "images": record.get("images"),
            "previous_hash": previous_hash,
            "published_at": record.get("published_at"),
            "source_id": record.get("source_id"),
            "source_url": record.get("source_url"),
            "title": record.get("title"),
        }

    def extract_image_urls(self, item: dict[str, Any]) -> list[str]:
        """Sammle Bild-URLs aus den <img>-Tags des content_html."""

        content_html = item.get("content_html")
        if not isinstance(content_html, str) or not content_html.strip():
            return []

        parser = _ImgTagParser()
        parser.feed(content_html)

        urls: list[str] = []
        seen: set[str] = set()
        for url in parser.urls:
            if url and url not in seen:
                urls.append(url)
                seen.add(url)
        return urls

    def _published_prefix(self, published_at: Any, storage_name: str | None = None) -> str:
        """Bilde einen dateisystemtauglichen Prefix aus dem Veroeffentlichungszeitpunkt."""

        text = str(published_at or "unknown")
        try:
            normalized = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            prefix = re.sub(r"[^0-9A-Za-z]+", "", text)
            timestamp = prefix or "unknown"
        else:
            timestamp = normalized.strftime("%Y%m%dT%H%M%S")

        return f"{storage_name}-{timestamp}" if storage_name else timestamp

    def _image_extension(self, url: str, content_type: str | None) -> str:
        """Ermittle eine passende Dateiendung fuer ein Bild."""

        extension = guess_extension(content_type or "") or Path(urlparse(url).path).suffix or ".bin"
        return extension.lower()

    def _find_existing_image(self, image_root: Path, prefix: str, image_hash: str) -> Path | None:
        """Suche eine bereits gespeicherte Bilddatei mit identischem Inhalt."""

        if not image_root.exists():
            return None

        for existing_path in sorted(image_root.glob(f"{prefix}-*")):
            if existing_path.is_file() and hashlib.sha256(existing_path.read_bytes()).hexdigest() == image_hash:
                return existing_path
        return None

    def _next_image_index(self, image_root: Path, prefix: str) -> int:
        """Bestimme die naechste freie Bildnummer fuer einen Prefix."""

        highest = 0
        if image_root.exists():
            for path in image_root.glob(f"{prefix}-*"):
                match = re.search(r"-(\d+)\.", path.name)
                if match:
                    highest = max(highest, int(match.group(1)))
        return highest + 1

    def download_image(
        self, url: str, image_root: Path, published_at: Any, counter: int, storage_name: str | None = None
    ) -> tuple[str, str, bytes]:
        """Lade ein Bild herunter, speichere es und gib Pfad, Hash und Rohbytes zurueck."""

        image_bytes, content_type = self.fetch_image(url)
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        prefix = self._published_prefix(published_at, storage_name)

        existing_path = self._find_existing_image(image_root, prefix, image_hash)
        if existing_path is not None:
            return str(existing_path), image_hash, image_bytes

        image_root.mkdir(parents=True, exist_ok=True)
        extension = self._image_extension(url, content_type)

        file_counter = counter
        while True:
            image_path = image_root / f"{prefix}-{file_counter:04d}{extension}"
            if not image_path.exists():
                break
            file_counter += 1

        image_path.write_bytes(image_bytes)
        return str(image_path), image_hash, image_bytes

    def _collect_images(
        self, item: dict[str, Any], published_at: Any, storage_root: Path, image_root: Path, storage_name: str | None = None
    ) -> tuple[dict[str, dict[str, str]], dict[str, bytes]]:
        """Lade alle Bilder eines Items herunter und baue das images-Dict sowie die Rohbytes je Hash."""

        image_urls = self.extract_image_urls(item)
        images: dict[str, dict[str, str]] = {}
        image_bytes_by_hash: dict[str, bytes] = {}
        if not image_urls:
            return images, image_bytes_by_hash

        prefix = self._published_prefix(published_at, storage_name)
        next_index = self._next_image_index(image_root, prefix)

        for image_url in image_urls:
            try:
                image_path, image_hash, image_bytes = self.download_image(image_url, image_root, published_at, next_index, storage_name)
            except Exception:
                continue

            relative_path = str(Path(image_path).relative_to(storage_root))
            images[image_hash] = {"url": image_url, "path": relative_path}
            image_bytes_by_hash[image_hash] = image_bytes
            next_index += 1

        return images, image_bytes_by_hash

    def prepare_item(
        self,
        item: dict[str, Any],
        retrieved_at: str,
        storage_root: Path,
        image_root: Path,
        storage_name: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, bytes]]:
        """Normalisiere ein Feed-Item und lade Bilder, ohne previous_hash/hash zu setzen.

        Das Ergebnis ist unabhaengig von einer konkreten Hash-Kette und kann fuer
        mehrere, getrennt gefuehrte Ketten (z.B. JSONL und SQLite) wiederverwendet werden.
        """

        rssbridge = item.get("_rssbridge") or {}
        dc = rssbridge.get("dc") or {}
        author = item.get("author") or {}

        source_id = str(item["id"])
        source_url = str(item.get("url") or rssbridge.get("link") or "")
        title = str(item.get("title") or "")
        content = str(item.get("content_html") or "")
        author_name = author.get("name") if isinstance(author, dict) else None
        raw_published_at = dc.get("date") or rssbridge.get("pubDate") or rssbridge.get("published") or rssbridge.get("updated")
        published_at = self.normalize_timestamp(raw_published_at) if raw_published_at else None

        images, image_bytes_by_hash = self._collect_images(item, published_at, storage_root, image_root, storage_name)

        prepared_item = {
            "codec_name": self.codec_name,
            "source_id": source_id,
            "source_url": source_url,
            "title": title,
            "content": content,
            "author_name": author_name,
            "published_at": str(published_at) if published_at else None,
            "retrieved_at": retrieved_at,
            "images": images,
        }
        return prepared_item, image_bytes_by_hash

    def finalize_record(self, prepared_item: dict[str, Any], previous_hash: str) -> dict[str, Any]:
        """Ergaenze previous_hash an einem vorbereiteten Item und berechne den verketteten Hash."""

        record = dict(prepared_item)
        record["previous_hash"] = previous_hash
        record["hash"] = self.digest_record(self.record_hash_material(record, previous_hash))
        return record

    def build_record(
        self,
        item: dict[str, Any],
        retrieved_at: str,
        previous_hash: str,
        storage_root: Path,
        image_root: Path,
        storage_name: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, bytes]]:
        """Normalisiere ein Feed-Item, lade Bilder und bilde den verketteten Record-Hash in einem Schritt."""

        prepared_item, image_bytes_by_hash = self.prepare_item(item, retrieved_at, storage_root, image_root)
        record = self.finalize_record(prepared_item, previous_hash)
        return record, image_bytes_by_hash

    def verify_record_hash_chain(self, records: list[dict[str, Any]]) -> bool:
        """Pruefe, ob alle Records eine konsistente Hash-Kette bilden."""

        previous_hash = GENESIS_HASH
        for record in records:
            expected_hash = self.digest_record(self.record_hash_material(record, previous_hash))
            if str(record.get("previous_hash")) != previous_hash:
                return False
            if str(record.get("hash")) != expected_hash:
                return False
            previous_hash = expected_hash
        return True


class _VersionedCodecMixin:
    """Ergaenze Records um versionierte JSON-Metadaten und deren Hashes."""

    def prepare_item(
        self,
        item: dict[str, Any],
        retrieved_at: str,
        storage_root: Path,
        image_root: Path,
        storage_name: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, bytes]]:
        prepared_item, image_bytes_by_hash = super().prepare_item(item, retrieved_at, storage_root, image_root, storage_name)
        prepared_item.update(metadata_hashes(storage_root, self.codec_name))
        return prepared_item, image_bytes_by_hash

    def record_hash_material(self, record: dict[str, Any], previous_hash: str) -> dict[str, Any]:
        material = super().record_hash_material(record, previous_hash)
        material.update(
            {
                "schema_hash": record.get("schema_hash"),
                "codec_hash": record.get("codec_hash"),
                "hash_function_hash": record.get("hash_function_hash"),
            }
        )
        return material


class TAZv0(RSSv0):
    """RSSv0-Codec, der TAZ-Links durch vollständige Artikelinhalte ersetzt."""

    codec_name = "TAZv0"

    def fetch_taz_article(self, url: str) -> str:
        """Lade den TAZ-Artikel und extrahiere den strukturierten Artikeltext."""

        response = None
        last_error: requests.RequestException | None = None
        for attempt in range(3):
            try:
                response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=REQUEST_TIMEOUT_SECONDS)
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(2**attempt)
        if response is None:
            raise last_error or RuntimeError("TAZ article request failed")
        scripts = re.findall(r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", response.text, re.DOTALL | re.IGNORECASE)
        article_body = ""
        image_url = ""
        for script in scripts:
            try:
                metadata = json.loads(script)
            except json.JSONDecodeError:
                continue
            candidates = metadata if isinstance(metadata, list) else [metadata]
            for candidate in candidates:
                if not isinstance(candidate, dict) or not candidate.get("articleBody"):
                    continue
                article_body = str(candidate["articleBody"]).strip()
                image = candidate.get("image")
                if isinstance(image, list) and image:
                    image_url = str(image[0])
                elif isinstance(image, str):
                    image_url = image
                break
            if article_body:
                break
        if not article_body:
            raise ValueError("TAZ article does not contain an articleBody")
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", article_body) if part.strip()]
        content = "".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs)
        if image_url:
            content += f'<img src="{html.escape(image_url, quote=True)}">'
        return content

    def prepare_item(
        self,
        item: dict[str, Any],
        retrieved_at: str,
        storage_root: Path,
        image_root: Path,
        storage_name: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, bytes]]:
        """Lade vor der Standardnormalisierung den vollständigen TAZ-Artikel."""

        enriched_item = dict(item)
        enriched_item["content_html"] = self.fetch_taz_article(str(item.get("url") or ""))
        return super().prepare_item(enriched_item, retrieved_at, storage_root, image_root, storage_name)


class RSSv1(_VersionedCodecMixin, RSSv0):
    """RSSv1 mit versionierten Schema-, Codec- und Hashmetadaten."""

    codec_name = "RSSv1"


class TAZv1(_VersionedCodecMixin, TAZv0):
    """TAZv1 mit versionierten Schema-, Codec- und Hashmetadaten."""

    codec_name = "TAZv1"


class SCREENv0(RSSv0):
    """Codec, der pro Quellenlauf einen vollständigen Seiten-Screenshot speichert."""

    codec_name = "SCREENv0"

    def fetch_feed(self, url: str) -> dict[str, Any]:
        """Begrenze den Screenshot-Lauf auf den ersten Eintrag des Feeds."""

        feed = super().fetch_feed(url)
        return {**feed, "items": feed.get("items", [])[:1]}

    def capture_screenshot(self, url: str, path: Path) -> bytes:
        """Rendere eine Seite mit Chromium und speichere sie vollständig als PNG."""

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError("SCREENv0 requires Playwright and an installed Chromium browser") from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            try:
                page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
                page.goto(url, wait_until="domcontentloaded", timeout=REQUEST_TIMEOUT_SECONDS * 1000)
                page.wait_for_timeout(2000)
                page.add_style_tag(content="*,:before,:after { animation: none !important; transition: none !important; }")
                page.evaluate(
                    """() => {
                        const selectors = [
                            "#consent-manager", "#consent-layer", "#onetrust-banner-sdk",
                            "#usercentrics-root", "#sp_message_container", ".cmp-consent",
                            "[id^='sp_message_container']",
                            "[id*='cookie' i]", "[class*='cookie' i]", "[id*='consent' i]",
                            "[class*='consent' i]"
                        ];
                        document.querySelectorAll(selectors.join(",")).forEach((element) => element.remove());
                        const zdfConsent = document.querySelector("#cmp-dialog");
                        if (zdfConsent) {
                            const dialog = zdfConsent.closest('[role="dialog"]');
                            const overlay = dialog?.parentElement?.parentElement;
                            (overlay || dialog || zdfConsent).remove();
                        }
                    }"""
                )
                path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(path), full_page=True, type="png", timeout=60_000)
            finally:
                browser.close()
        return path.read_bytes()

    def prepare_item(
        self,
        item: dict[str, Any],
        retrieved_at: str,
        storage_root: Path,
        image_root: Path,
        storage_name: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, bytes]]:
        """Erzeuge den Record und ergänze den vollständigen Seiten-Screenshot."""

        enriched_item = dict(item)
        enriched_item["content_html"] = ""
        prepared_item, image_bytes_by_hash = super().prepare_item(enriched_item, retrieved_at, storage_root, image_root, storage_name)
        published_at = prepared_item["published_at"]
        prefix = self._published_prefix(published_at, storage_name)
        screenshot_path = image_root / f"{prefix}-screenshot.png"
        screenshot_bytes = self.capture_screenshot(str(item["url"]), screenshot_path)
        image_hash = hashlib.sha256(screenshot_bytes).hexdigest()
        prepared_item["images"][image_hash] = {
            "url": str(item["url"]),
            "path": str(screenshot_path.relative_to(storage_root)),
        }
        image_bytes_by_hash[image_hash] = screenshot_bytes
        return prepared_item, image_bytes_by_hash


class SCREENv1(_VersionedCodecMixin, SCREENv0):
    """SCREENv1 mit versionierten Schema-, Codec- und Hashmetadaten."""

    codec_name = "SCREENv1"


class RSSv2(_VersionedCodecMixin, RSSv0):
    """RSSv2 mit einem individuellen normalisierten Codecvertrag."""

    codec_name = "RSSv2"


class TAZv2(_VersionedCodecMixin, TAZv0):
    """TAZv2 mit einem individuellen normalisierten Codecvertrag."""

    codec_name = "TAZv2"


class SCREENv2(_VersionedCodecMixin, SCREENv0):
    """SCREENv2 mit einem individuellen normalisierten Codecvertrag."""

    codec_name = "SCREENv2"


CODEC_REGISTRY: dict[str, RSSv0] = {
    "RSSv2": RSSv2(),
    "TAZv2": TAZv2(),
    "SCREENv2": SCREENv2(),
}
VALIDATION_CODEC_REGISTRY: dict[str, RSSv0] = {
    "RSSv0": RSSv0(),
    "TAZv0": TAZv0(),
    "SCREENv0": SCREENv0(),
    "RSSv1": RSSv1(),
    "TAZv1": TAZv1(),
    "SCREENv1": SCREENv1(),
    **CODEC_REGISTRY,
}
DEFAULT_CODEC = CODEC_REGISTRY["RSSv2"]


def get_codec(name: str) -> RSSv0:
    """Hole einen aktiven Codec fuer neue Verarbeitung per Namen."""

    try:
        return CODEC_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported codec: {name}") from exc


def get_validation_codec(name: str) -> RSSv0:
    """Hole einen aktiven oder historischen Codec fuer die Validierung."""

    try:
        return VALIDATION_CODEC_REGISTRY[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported validation codec: {name}") from exc
