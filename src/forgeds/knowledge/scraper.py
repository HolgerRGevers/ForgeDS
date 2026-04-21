"""Zoho documentation scraper.

Fetches HTML from Zoho help pages, converts to markdown, and writes
to raw_md/ with YAML frontmatter. Supports incremental re-scraping
via _manifest.json (ETag / Last-Modified tracking).

Features:
- follow_links: crawl index pages and discover leaf documentation pages
- Domain normalization: canonical URLs across Zoho's dual-domain setup
- Parallel scraping: per-module threads with staggered starts and jittered delays

HTTP: urllib.request (stdlib).
HTML -> MD: html.parser (stdlib) with optional beautifulsoup4 + markdownify.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import random
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from forgeds._shared.config import find_project_root, load_config

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Security: URL validation to prevent SSRF
# ---------------------------------------------------------------------------

_ALLOWED_SCHEMES = {"http", "https"}


def _is_safe_url(url: str) -> bool:
    """Reject file://, ftp://, and private/loopback IP targets."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Resolve hostname and reject private/loopback IPs
    try:
        for info in socket.getaddrinfo(hostname, None):
            addr = ipaddress.ip_address(info[4][0])
            if addr.is_private or addr.is_loopback or addr.is_reserved or addr.is_link_local:
                return False
    except (socket.gaierror, ValueError):
        return False

    return True


# ---------------------------------------------------------------------------
# Dual-domain URL normalization
# ---------------------------------------------------------------------------

# Zoho serves identical content on multiple domains.
# We canonicalize to www.zoho.com to prevent duplicate tokens.
_DOMAIN_CANONICAL: dict[str, str] = {
    "deluge.zoho.com": "www.zoho.com",
}

_domain_verified: dict[str, bool] = {}
_domain_lock = threading.Lock()


def _normalize_zoho_url(url: str) -> str:
    """Rewrite known Zoho alias domains to the canonical form.

    Only rewrites after domain equivalence has been verified via
    ``verify_domain_equivalence``. Until verified, returns the URL unchanged.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    canonical = _DOMAIN_CANONICAL.get(hostname)
    if not canonical:
        return url

    with _domain_lock:
        verified = _domain_verified.get(hostname)

    if verified is None or verified is False:
        return url  # not yet verified — leave as-is

    return url.replace(f"//{hostname}", f"//{canonical}", 1)


def verify_domain_equivalence(
    urls: list[str],
    sample_ratio: float = 0.3,
) -> dict[str, bool]:
    """Sample *sample_ratio* of *urls* to confirm alias domains serve the
    same content as their canonical counterpart.

    Fetches the page from both domains, compares a SHA-256 of the
    stripped body text. Returns a dict of ``{alias_domain: True/False}``.
    Results are cached in ``_domain_verified`` and used by
    ``_normalize_zoho_url`` to gate rewrites.
    """
    from collections import defaultdict
    alias_urls: dict[str, list[str]] = defaultdict(list)

    for url in urls:
        hostname = urlparse(url).hostname or ""
        if hostname in _DOMAIN_CANONICAL:
            alias_urls[hostname].append(url)

    results: dict[str, bool] = {}
    for alias, pool in alias_urls.items():
        canonical = _DOMAIN_CANONICAL[alias]
        n = max(1, int(len(pool) * sample_ratio))
        sample = random.sample(pool, min(n, len(pool)))

        matches = 0
        total = 0
        for url in sample:
            alias_html = _fetch_body_text(url)
            canon_url = url.replace(f"//{alias}", f"//{canonical}", 1)
            canon_html = _fetch_body_text(canon_url)
            if alias_html and canon_html:
                total += 1
                if _content_hash(alias_html) == _content_hash(canon_html):
                    matches += 1

        equiv = total > 0 and (matches / total) >= 0.8
        results[alias] = equiv

        with _domain_lock:
            _domain_verified[alias] = equiv

        log.info(
            "Domain equivalence %s↔%s: %d/%d matched → %s",
            alias, canonical, matches, total,
            "EQUIVALENT" if equiv else "DIFFERENT",
        )

    return results


def _fetch_body_text(url: str) -> str | None:
    """Fetch a URL and return the raw body text, or None on failure."""
    if not _is_safe_url(url):
        return None
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "ForgeDS-KB-Scraper/0.1")
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _content_hash(text: str) -> str:
    """SHA-256 of whitespace-normalized text for content comparison."""
    normalized = re.sub(r"\s+", " ", text.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Link extraction for follow_links crawling
# ---------------------------------------------------------------------------

class _LinkExtractor(HTMLParser):
    """Extract <a href> links from HTML content."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        if tag == "a":
            for name, val in attrs:
                if name == "href" and val:
                    self.links.append(val)


def _extract_doc_links(
    html: str,
    base_url: str,
    same_section_only: bool = True,
) -> list[str]:
    """Extract documentation links from HTML.

    Resolves relative URLs against *base_url*. When *same_section_only*
    is True (default), only returns links that share the same path prefix
    as the base URL (e.g. ``/deluge/help/functions/`` stays within
    ``/deluge/help/``).

    Filters out anchors (#), non-html links, and external domains.
    """
    extractor = _LinkExtractor()
    extractor.feed(html)

    base_parsed = urlparse(base_url)
    # Use path up to last segment as the allowed prefix
    base_prefix = base_parsed.path.rsplit("/", 1)[0] if "/" in base_parsed.path else base_parsed.path
    base_domain = base_parsed.hostname or ""

    # Also accept alias domains as "same domain"
    accepted_domains = {base_domain}
    for alias, canonical in _DOMAIN_CANONICAL.items():
        if base_domain == canonical:
            accepted_domains.add(alias)
        elif base_domain == alias:
            accepted_domains.add(canonical)

    seen: set[str] = set()
    result: list[str] = []

    for raw_href in extractor.links:
        # Skip pure anchors and javascript
        if raw_href.startswith("#") or raw_href.startswith("javascript:"):
            continue

        absolute = urljoin(base_url, raw_href)
        # Strip fragment
        absolute = absolute.split("#")[0]
        # Normalize trailing slash
        if absolute.endswith("/"):
            absolute = absolute.rstrip("/")

        parsed = urlparse(absolute)
        link_domain = parsed.hostname or ""

        # Must be same domain (or known alias)
        if link_domain not in accepted_domains:
            continue

        # Must be an HTML doc page
        path = parsed.path
        if path and not (path.endswith(".html") or path.endswith("/")):
            ext = path.rsplit(".", 1)[-1] if "." in path.rsplit("/", 1)[-1] else ""
            if ext and ext not in ("html", "htm", ""):
                continue

        # Optionally restrict to same path section
        if same_section_only and not path.startswith(base_prefix):
            continue

        # Normalize domain to canonical for dedup
        normalized = _normalize_zoho_url(absolute)
        if normalized not in seen:
            seen.add(normalized)
            result.append(absolute)

    return result


# ---------------------------------------------------------------------------
# Breadcrumb / hierarchy helpers
# ---------------------------------------------------------------------------

def _build_breadcrumb(url: str, parent_url: str | None, module: str) -> list[str]:
    """Build a breadcrumb trail from module root to this URL.

    Returns a list like ["deluge", "/deluge/help/functions/text.html",
    "/deluge/help/functions/string/contains.html"].
    """
    crumbs = [module]
    if parent_url:
        crumbs.append(parent_url)
    crumbs.append(url)
    return crumbs


def _escape_yaml_value(value: str) -> str:
    """Escape a string for safe inclusion in YAML frontmatter."""
    # Replace backslashes first, then quotes and newlines
    value = value.replace("\\", "\\\\")
    value = value.replace('"', '\\"')
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "")
    return value


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def _manifest_path(raw_md_dir: Path) -> Path:
    return raw_md_dir / "_manifest.json"


def load_manifest(raw_md_dir: Path) -> dict:
    mp = _manifest_path(raw_md_dir)
    if mp.exists():
        return json.loads(mp.read_text(encoding="utf-8"))
    return {"pages": {}}


def save_manifest(raw_md_dir: Path, manifest: dict) -> None:
    mp = _manifest_path(raw_md_dir)
    mp.parent.mkdir(parents=True, exist_ok=True)
    mp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Minimal HTML -> Markdown converter (stdlib only)
# ---------------------------------------------------------------------------

class _HtmlToMd(HTMLParser):
    """Converts a subset of HTML to markdown.

    Handles: headings, paragraphs, links, bold, italic, code blocks,
    lists, tables, and Zoho callout divs. Not a full converter — just
    enough to produce parseable markdown from Zoho help pages.
    """

    def __init__(self) -> None:
        super().__init__()
        self._out: list[str] = []
        self._tag_stack: list[str] = []
        self._href: Optional[str] = None
        self._link_text: list[str] = []
        self._in_link = False
        self._in_pre = False
        self._list_depth = 0
        self._heading_level = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, Optional[str]]]) -> None:
        self._tag_stack.append(tag)
        attr_dict = dict(attrs)

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._heading_level = int(tag[1])
            self._out.append("\n" + "#" * self._heading_level + " ")
        elif tag == "p":
            self._out.append("\n\n")
        elif tag == "br":
            self._out.append("\n")
        elif tag == "a":
            self._in_link = True
            self._href = attr_dict.get("href", "")
            self._link_text = []
        elif tag in ("strong", "b"):
            self._out.append("**")
        elif tag in ("em", "i"):
            self._out.append("*")
        elif tag == "code" and not self._in_pre:
            self._out.append("`")
        elif tag == "pre":
            self._in_pre = True
            self._out.append("\n```\n")
        elif tag in ("ul", "ol"):
            self._list_depth += 1
        elif tag == "li":
            indent = "  " * (self._list_depth - 1)
            self._out.append(f"\n{indent}- ")
        elif tag == "table":
            self._out.append("\n")
        elif tag == "tr":
            self._out.append("| ")
        elif tag in ("td", "th"):
            pass  # content handled by handle_data
        elif tag == "div":
            cls = attr_dict.get("class", "")
            if any(k in cls for k in ("note", "tip", "important")):
                self._out.append("\n> ")

    def handle_endtag(self, tag: str) -> None:
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._out.append("\n")
            self._heading_level = 0
        elif tag == "a":
            text = "".join(self._link_text)
            self._out.append(f"[{text}]({self._href})")
            self._in_link = False
            self._href = None
            self._link_text = []
        elif tag in ("strong", "b"):
            self._out.append("**")
        elif tag in ("em", "i"):
            self._out.append("*")
        elif tag == "code" and not self._in_pre:
            self._out.append("`")
        elif tag == "pre":
            self._in_pre = False
            self._out.append("\n```\n")
        elif tag in ("ul", "ol"):
            self._list_depth = max(0, self._list_depth - 1)
        elif tag in ("td", "th"):
            self._out.append(" | ")
        elif tag == "tr":
            self._out.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_link:
            self._link_text.append(data)
        elif self._in_pre:
            self._out.append(data)
        else:
            self._out.append(data)

    def get_markdown(self) -> str:
        text = "".join(self._out)
        # Collapse excessive blank lines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


def html_to_markdown(html: str) -> str:
    """Convert HTML to markdown using the stdlib-only converter.

    If beautifulsoup4 and markdownify are installed (via the
    [knowledge] extras group), use those for higher fidelity.
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore[import-untyped]
        from markdownify import markdownify as md  # type: ignore[import-untyped]

        soup = BeautifulSoup(html, "html.parser")
        # Strip nav, footer, and sidebar — keep main content
        for tag in soup.find_all(["nav", "footer", "aside", "script", "style"]):
            tag.decompose()
        main = soup.find("main") or soup.find("article") or soup.find("div", class_="help-content") or soup
        return md(str(main), heading_style="ATX", strip=["img"]).strip() + "\n"
    except ImportError:
        pass

    parser = _HtmlToMd()
    parser.feed(html)
    return parser.get_markdown()


def _extract_title(md_text: str) -> str:
    """Pull the first H1 from markdown text."""
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def _url_to_md_path(url: str, module: str) -> str:
    """Convert a URL to a relative path under raw_md/."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "_")
    if not path:
        path = "index"
    return f"{module}/{path}.md"


def fetch_page(url: str, manifest_entry: dict | None = None) -> tuple[str | None, dict]:
    """Fetch a URL, respecting ETag/Last-Modified for conditional requests.

    Returns (html_content_or_None, updated_manifest_entry).
    html_content is None if the server returned 304 Not Modified.

    Raises ValueError if the URL scheme is not http/https or targets a
    private/loopback address (SSRF protection).
    """
    if not _is_safe_url(url):
        raise ValueError(
            f"Refused to fetch URL: {url!r} — only http/https to public hosts allowed"
        )

    req = urllib.request.Request(url, method="GET")
    req.add_header("User-Agent", "ForgeDS-KB-Scraper/0.1")

    if manifest_entry:
        if manifest_entry.get("etag"):
            req.add_header("If-None-Match", manifest_entry["etag"])
        if manifest_entry.get("last_modified"):
            req.add_header("If-Modified-Since", manifest_entry["last_modified"])

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8", errors="replace")
            entry = {
                "url": url,
                "etag": resp.headers.get("ETag", ""),
                "last_modified": resp.headers.get("Last-Modified", ""),
                "scraped_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "status": resp.status,
            }
            return html, entry
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, manifest_entry or {}
        raise


# ---------------------------------------------------------------------------
# Scrape orchestration
# ---------------------------------------------------------------------------

def _jittered_delay(min_s: float = 2.0, max_s: float = 5.0) -> None:
    """Sleep for a random duration between *min_s* and *max_s* seconds."""
    time.sleep(random.uniform(min_s, max_s))


def _scrape_single(
    url: str,
    module: str,
    raw_md_dir: Path,
    manifest: dict,
    manifest_lock: threading.Lock,
    force: bool = False,
    parent_url: str | None = None,
) -> str | None:
    """Scrape a single URL and write the markdown file.

    Returns the relative md path if written, or None if skipped (304).
    Thread-safe: uses *manifest_lock* around manifest reads/writes.
    """
    # Normalize URL for canonical dedup
    canonical_url = _normalize_zoho_url(url)
    md_rel = _url_to_md_path(canonical_url, module)

    with manifest_lock:
        existing = manifest["pages"].get(canonical_url)

    if existing and not force:
        html, entry = fetch_page(url, existing)
    else:
        html, entry = fetch_page(url)

    with manifest_lock:
        manifest["pages"][canonical_url] = entry

    if html is None:
        return None  # 304 Not Modified

    md_text = html_to_markdown(html)
    title = _extract_title(md_text)
    breadcrumb = _build_breadcrumb(canonical_url, parent_url, module)

    # Write with YAML frontmatter including hierarchy info
    frontmatter = (
        "---\n"
        f"url: \"{_escape_yaml_value(canonical_url)}\"\n"
        f"title: \"{_escape_yaml_value(title)}\"\n"
        f"module: \"{_escape_yaml_value(module)}\"\n"
        f"parent_url: \"{_escape_yaml_value(parent_url or '')}\"\n"
        f"breadcrumb: \"{_escape_yaml_value(' > '.join(breadcrumb))}\"\n"
        f"scraped_at: \"{_escape_yaml_value(entry['scraped_at'])}\"\n"
        f"etag: \"{_escape_yaml_value(entry.get('etag', ''))}\"\n"
        f"last_modified: \"{_escape_yaml_value(entry.get('last_modified', ''))}\"\n"
        "---\n\n"
    )

    out_path = raw_md_dir / md_rel
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(frontmatter + md_text, encoding="utf-8")
    return md_rel


def _crawl_with_follow(
    seed_url: str,
    module: str,
    raw_md_dir: Path,
    manifest: dict,
    manifest_lock: threading.Lock,
    force: bool = False,
    max_depth: int = 2,
) -> list[str]:
    """Crawl starting from *seed_url*, following documentation links.

    Discovers leaf pages from index/hub pages up to *max_depth* levels.
    Each discovered page records its parent_url for hierarchy tracking.

    Returns list of written md file paths.
    """
    written: list[str] = []
    visited: set[str] = set()
    # Queue entries: (url, parent_url, depth)
    queue: list[tuple[str, str | None, int]] = [(seed_url, None, 0)]

    while queue:
        url, parent_url, depth = queue.pop(0)
        canonical = _normalize_zoho_url(url)

        if canonical in visited:
            continue
        visited.add(canonical)

        log.info("[%s] depth=%d scraping %s", module, depth, url)

        try:
            # Fetch HTML for both writing AND link discovery
            html_raw, _entry = fetch_page(url)
        except Exception as exc:
            log.warning("[%s] Failed to fetch %s: %s", module, url, exc)
            _jittered_delay()
            continue

        # Write the markdown file
        try:
            md_rel = _scrape_single(
                url, module, raw_md_dir, manifest, manifest_lock,
                force=force, parent_url=parent_url,
            )
            if md_rel:
                written.append(md_rel)
        except Exception as exc:
            log.warning("[%s] Failed to write %s: %s", module, url, exc)

        # Discover child links if we haven't hit max depth
        if depth < max_depth and html_raw:
            child_links = _extract_doc_links(html_raw, url, same_section_only=True)
            for child_url in child_links:
                child_canonical = _normalize_zoho_url(child_url)
                if child_canonical not in visited:
                    queue.append((child_url, canonical, depth + 1))

        _jittered_delay()

    return written


def _scrape_module(
    module_sources: list[dict],
    module_name: str,
    raw_md_dir: Path,
    manifest: dict,
    manifest_lock: threading.Lock,
    force: bool = False,
    follow_links: bool = False,
    max_depth: int = 2,
) -> list[str]:
    """Scrape all sources for a single module. Runs in its own thread."""
    written: list[str] = []

    for src in module_sources:
        url = src["url"]
        fl = src.get("follow_links", follow_links)

        if fl:
            results = _crawl_with_follow(
                url, module_name, raw_md_dir, manifest, manifest_lock,
                force=force, max_depth=src.get("max_depth", max_depth),
            )
            written.extend(results)
        else:
            try:
                md_rel = _scrape_single(
                    url, module_name, raw_md_dir, manifest, manifest_lock,
                    force=force,
                )
                if md_rel:
                    written.append(md_rel)
            except Exception as exc:
                log.warning("[%s] Failed %s: %s", module_name, url, exc)

            _jittered_delay()

    return written


def scrape_sources(
    sources: list[dict],
    raw_md_dir: Path,
    delay: float = 2.0,
    force: bool = False,
    follow_links: bool = False,
    parallel: bool = False,
    max_depth: int = 2,
    verify_domains: bool = True,
) -> list[str]:
    """Scrape a list of URL sources into raw_md/.

    Each source dict must have: ``url``, ``module``.
    Optional per-source keys: ``follow_links`` (bool), ``max_depth`` (int).

    Parameters
    ----------
    follow_links : bool
        When True, index pages are crawled for child documentation links.
        Can also be set per-source in the source dict.
    parallel : bool
        When True, each module is scraped in a separate thread, with
        starts staggered over 60 seconds and random 2–5 s delays
        between requests within each module.
    verify_domains : bool
        When True, runs a 30 % sampling check to confirm Zoho alias
        domains serve identical content before normalizing URLs.
    max_depth : int
        Maximum crawl depth for follow_links (default 2).

    Returns list of written md file paths (relative to raw_md_dir).
    """
    manifest = load_manifest(raw_md_dir)
    manifest_lock = threading.Lock()

    # --- Domain equivalence verification ---
    if verify_domains:
        all_urls = [s["url"] for s in sources]
        verify_domain_equivalence(all_urls, sample_ratio=0.3)

    # --- Group sources by module ---
    from collections import defaultdict
    by_module: dict[str, list[dict]] = defaultdict(list)
    for src in sources:
        by_module[src.get("module", "deluge")].append(src)

    written: list[str] = []

    if parallel and len(by_module) > 1:
        # Stagger module starts over 60 seconds
        module_names = list(by_module.keys())
        stagger_interval = 60.0 / len(module_names) if len(module_names) > 1 else 0

        with ThreadPoolExecutor(max_workers=len(module_names)) as executor:
            futures = {}
            for i, mod_name in enumerate(module_names):
                # Submit with staggered start — each thread sleeps before beginning
                stagger_delay = i * stagger_interval
                futures[executor.submit(
                    _parallel_module_worker,
                    by_module[mod_name], mod_name, raw_md_dir,
                    manifest, manifest_lock,
                    force, follow_links, max_depth, stagger_delay,
                )] = mod_name

            for future in as_completed(futures):
                mod_name = futures[future]
                try:
                    result = future.result()
                    written.extend(result)
                    log.info("[%s] completed: %d page(s)", mod_name, len(result))
                except Exception as exc:
                    log.error("[%s] module scrape failed: %s", mod_name, exc)
    else:
        # Sequential scraping (single module or parallel=False)
        for mod_name, mod_sources in by_module.items():
            result = _scrape_module(
                mod_sources, mod_name, raw_md_dir,
                manifest, manifest_lock,
                force=force, follow_links=follow_links, max_depth=max_depth,
            )
            written.extend(result)

    save_manifest(raw_md_dir, manifest)
    return written


def _parallel_module_worker(
    module_sources: list[dict],
    module_name: str,
    raw_md_dir: Path,
    manifest: dict,
    manifest_lock: threading.Lock,
    force: bool,
    follow_links: bool,
    max_depth: int,
    stagger_delay: float,
) -> list[str]:
    """Thread entry point — waits for stagger then scrapes the module."""
    if stagger_delay > 0:
        log.info("[%s] staggering start by %.1fs", module_name, stagger_delay)
        time.sleep(stagger_delay)

    log.info("[%s] starting scrape (%d source(s))", module_name, len(module_sources))
    return _scrape_module(
        module_sources, module_name, raw_md_dir,
        manifest, manifest_lock,
        force=force, follow_links=follow_links, max_depth=max_depth,
    )


def get_scrape_config() -> tuple[list[dict], Path, float, bool, bool, int]:
    """Read scrape configuration from forgeds.yaml.

    Expected config shape::

        knowledge:
            raw_md_dir: raw_md
            scrape_delay: 2
            follow_links: true
            parallel: true
            max_depth: 2
            sources:
                - url: https://...
                  module: deluge
                  follow_links: true
                  max_depth: 3

    Returns (sources, raw_md_dir, delay, follow_links, parallel, max_depth).
    """
    config = load_config()
    kb = config.get("knowledge", {})

    root = find_project_root()
    raw_md_dir = root / kb.get("raw_md_dir", "raw_md")
    delay = float(kb.get("scrape_delay", 2.0))
    sources = kb.get("sources", [])
    follow_links = bool(kb.get("follow_links", False))
    parallel = bool(kb.get("parallel", False))
    max_depth = int(kb.get("max_depth", 2))

    return sources, raw_md_dir, delay, follow_links, parallel, max_depth
