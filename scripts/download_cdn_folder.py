#!/usr/bin/env python3
"""
Mirror a Construct 2 (or similar) game folder from a CDN for offline play.

It discovers:
  - images/*.(png|jpg|jpeg|gif|webp|svg) from HTML/JS and data.js
  - media/*.(m4a|ogg|mp3|wav) from data.js
  - core files (index.html, c2runtime.js, data.js, jquery, gamee-js, sw, manifest, icons)

Examples:
  python app/scripts/download_cdn_folder.py \\
    --base https://games.cdn.gamee.io/games/game-236/data \\
    --out app/webapp/arcade/superbugz_offline \\
    --kind all
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup  # type: ignore

# File types
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
AUDIO_EXTENSIONS = (".m4a", ".ogg", ".mp3", ".wav")

# Simple desktop-like UA and optional Referer (some CDNs require it)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    )
}


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def is_image_path(path: str) -> bool:
    return path.lower().endswith(IMAGE_EXTENSIONS)


def fetch_text(url: str, referer: Optional[str] = None, timeout: int = 25) -> Optional[str]:
    headers = dict(DEFAULT_HEADERS)
    if referer:
        headers["Referer"] = referer
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            resp.encoding = resp.apparent_encoding
            return resp.text
        return None
    except requests.RequestException:
        return None


def fetch_binary(url: str, referer: Optional[str] = None, timeout: int = 35) -> Optional[bytes]:
    headers = dict(DEFAULT_HEADERS)
    if referer:
        headers["Referer"] = referer
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.content
        return None
    except requests.RequestException:
        return None


def parse_directory_listing_for_images(listing_html: str, base_images_url: str) -> Set[str]:
    soup = BeautifulSoup(listing_html, "html.parser")
    found: Set[str] = set()
    for a in soup.find_all("a"):
        href = (a.get("href") or "").strip()
        if not href or href in ("../", "./", "/"):
            continue
        absolute = href
        if not href.startswith("http://") and not href.startswith("https://"):
            absolute = base_images_url.rstrip("/") + "/" + href.lstrip("/")
        if is_image_path(absolute):
            found.add(absolute)
    return found


# Find relative references like images/foo.png inside text blobs
IMAGE_PATH_REGEX = re.compile(
    r'images/[A-Za-z0-9_\-./]+\.(?:png|jpg|jpeg|gif|webp|svg)'
)


def extract_image_paths_from_text(text: str) -> Set[str]:
    return set(IMAGE_PATH_REGEX.findall(text or ""))


def extract_script_urls_from_html(html_text: str, base_url: str) -> List[str]:
    soup = BeautifulSoup(html_text, "html.parser")
    urls: List[str] = []
    for tag in soup.find_all(["script", "link"]):
        if tag.name == "script":
            src = tag.get("src")
            if not src:
                continue
            if src.startswith("http://") or src.startswith("https://"):
                urls.append(src)
            else:
                urls.append(base_url.rstrip("/") + "/" + src.lstrip("/"))
        elif tag.name == "link":
            rel = (tag.get("rel") or [""])[0]
            href = tag.get("href")
            if href and rel in ("stylesheet", "preload", "modulepreload"):
                if href.startswith("http://") or href.startswith("https://"):
                    urls.append(href)
                else:
                    urls.append(base_url.rstrip("/") + "/" + href.lstrip("/"))
    return urls


def _relpath_from_base(url: str, base_url: str) -> str:
    """Return the URL path part relative to base_url's path."""
    bu = urlparse(base_url)
    uu = urlparse(url)
    base_path = bu.path.rstrip("/")
    upath = uu.path
    if upath.startswith(base_path + "/"):
        return upath[len(base_path) + 1 :]
    return os.path.basename(upath)


def discover_image_urls(base_url: str) -> Set[str]:
    base_url = base_url.rstrip("/")
    images_url = base_url + "/images/"

    # Try directory listing first (if enabled on CDN bucket)
    listing_html = fetch_text(images_url, referer=base_url + "/index.html")
    if listing_html and "<a" in listing_html.lower():
        from_listing = parse_directory_listing_for_images(listing_html, images_url)
        if from_listing:
            return from_listing

    # Parse index + referenced scripts
    index_url = base_url + "/index.html"
    index_html = fetch_text(index_url)
    candidate_paths: Set[str] = set()
    scripts_to_scan: List[str] = []
    if index_html:
        scripts_to_scan.extend(extract_script_urls_from_html(index_html, base_url))
        candidate_paths.update(extract_image_paths_from_text(index_html))

    for script_url in scripts_to_scan:
        text = fetch_text(script_url, referer=index_url)
        if not text:
            continue
        candidate_paths.update(extract_image_paths_from_text(text))

    # Known Construct manifests
    for known_name in ("data.js", "data.json"):
        manifest_url = base_url + "/" + known_name
        text = fetch_text(manifest_url, referer=index_url)
        if text:
            candidate_paths.update(extract_image_paths_from_text(text))

    # Absolute URLs
    absolute_urls: Set[str] = set()
    for p in candidate_paths:
        if p.startswith("http://") or p.startswith("https://"):
            absolute_urls.add(p)
        else:
            absolute_urls.add(base_url + "/" + p.lstrip("/"))
    return {u for u in absolute_urls if is_image_path(u)}


def discover_media_urls(base_url: str) -> Set[str]:
    base_url = base_url.rstrip("/")
    index_url = base_url + "/index.html"
    media_paths: Set[str] = set()

    data_js = fetch_text(base_url + "/data.js", referer=index_url)
    if data_js:
        # Prefer explicit "media/..." references
        media_regex = re.compile(r"media/[A-Za-z0-9_\\-./]+\\.(?:m4a|ogg|mp3|wav)")
        matches = media_regex.findall(data_js)
        media_paths.update(matches)
        # Fallback: if files listed without the "media/" prefix, add it
        if not matches and '"media/"' in data_js:
            name_regex = re.compile(r'"([A-Za-z0-9_\\-./]+\\.(?:m4a|ogg|mp3|wav))"')
            for fname in name_regex.findall(data_js):
                if "/" in fname:
                    media_paths.add(fname)
                else:
                    media_paths.add(f"media/{fname}")

    absolute: Set[str] = set()
    for p in media_paths:
        if p.startswith("http://") or p.startswith("https://"):
            absolute.add(p)
        else:
            absolute.add(base_url + "/" + p)
    return absolute


CORE_FILES = (
    "index.html",
    "c2runtime.js",
    "data.js",
    "jquery-2.1.1.min.js",
    "gamee-js.min.js",
    "sw.js",
    "appmanifest.json",
    "loading-logo.png",
)


def discover_core_urls(base_url: str) -> Set[str]:
    base_url = base_url.rstrip("/")
    urls: Set[str] = set()

    # Add standard core files if they exist
    for name in CORE_FILES:
        u = base_url + "/" + name
        try:
            r = requests.head(u, headers=DEFAULT_HEADERS, timeout=12)
            if r.status_code == 200:
                urls.add(u)
        except requests.RequestException:
            pass

    # Parse index for extra scripts and icons
    index_html = fetch_text(base_url + "/index.html")
    if index_html:
        urls.update(extract_script_urls_from_html(index_html, base_url))
        # Icons referenced in HTML
        icon_regex = re.compile(r'href="(icon-[^"]+?\\.png)"')
        for m in icon_regex.findall(index_html):
            if m.startswith("http://") or m.startswith("https://"):
                urls.add(m)
            else:
                urls.add(base_url + "/" + m.lstrip("/"))

    # Icons from manifest
    manifest_text = fetch_text(base_url + "/appmanifest.json")
    if manifest_text:
        try:
            manifest = json.loads(manifest_text)
            for icon in manifest.get("icons", []):
                src = icon.get("src")
                if src:
                    if src.startswith("http://") or src.startswith("https://"):
                        urls.add(src)
                    else:
                        urls.add(base_url + "/" + src.lstrip("/"))
        except Exception:
            pass

    return urls


@dataclass
class DownloadResult:
    url: str
    ok: bool
    reason: str = ""


def download_one(url: str, output_dir: str, referer: Optional[str], base_url: Optional[str], flatten: bool) -> DownloadResult:
    try:
        data = fetch_binary(url, referer=referer)
        if data is None:
            return DownloadResult(url=url, ok=False, reason="HTTP error or empty body")
        if not flatten and base_url:
            # Preserve folder structure relative to base
            bu = base_url.rstrip("/")
            rel = _relpath_from_base(url, bu)
            save_path = os.path.join(output_dir, rel)
            ensure_dir(os.path.dirname(save_path))
        else:
            filename = os.path.basename(url.split("?", 1)[0])
            save_path = os.path.join(output_dir, filename)
        with open(save_path, "wb") as f:
            f.write(data)
        return DownloadResult(url=url, ok=True)
    except Exception as e:  # noqa: BLE001
        return DownloadResult(url=url, ok=False, reason=str(e))


def download_all(urls: Iterable[str], output_dir: str, referer: Optional[str], *, base_url: Optional[str], flatten: bool) -> Tuple[int, int]:
    ensure_dir(output_dir)
    successes = 0
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(download_one, u, output_dir, referer, base_url, flatten) for u in urls]
        for fut in concurrent.futures.as_completed(futures):
            res = fut.result()
            if res.ok:
                successes += 1
            else:
                failures += 1
                print(f"[WARN] Failed: {res.url} -> {res.reason}")
    return successes, failures


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mirror Construct2/CDN game folder for offline use")
    parser.add_argument("--base", required=True, help="Base URL to the game data folder (e.g., https://.../game-236/data)")
    parser.add_argument("--out", required=True, help="Local directory to save into (structure preserved by default)")
    parser.add_argument("--kind", choices=["images", "media", "core", "all"], default="all", help="What to download")
    parser.add_argument("--flat", action="store_true", help="Save all files flatly in the output dir instead of subfolders")
    args = parser.parse_args(argv)

    base_url = args.base.rstrip("/")
    out_dir = os.path.abspath(args.out)
    ensure_dir(out_dir)

    print(f"Discovering asset URLs from {base_url} ...")
    urls: Set[str] = set()
    if args.kind in ("images", "all"):
        urls.update(discover_image_urls(base_url))
    if args.kind in ("media", "all"):
        urls.update(discover_media_urls(base_url))
    if args.kind in ("core", "all"):
        urls.update(discover_core_urls(base_url))

    if not urls:
        print("No asset URLs discovered. Exiting with error.")
        return 2
    print(f"Discovered {len(urls)} file(s).")

    referer = base_url + "/index.html"
    print(f"Downloading to {out_dir} ...")
    ok, err = download_all(sorted(urls), out_dir, referer, base_url=base_url, flatten=args.flat)
    print(f"Done. Success: {ok}, Failed: {err}")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())


