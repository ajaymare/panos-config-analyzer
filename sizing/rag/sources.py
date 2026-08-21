"""Known PA datasheet URLs and web search fallback."""

import os
import logging
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

RAG_DATA_DIR = os.environ.get('RAG_DATA_DIR', '/app/rag_data')
PDF_DIR = os.path.join(RAG_DATA_DIR, 'pdfs')

# Known Palo Alto Networks datasheet PDF URLs (public).
# These are the official product spec sheet URLs from paloaltonetworks.com.
# Update this dict when new series are released.
DATASHEET_URLS = {
    'PA-400 Series': 'https://www.paloaltonetworks.com/resources/datasheets/pa-400-series',
    'PA-500 Series': 'https://www.paloaltonetworks.com/resources/datasheets/pa-400-series',
    'PA-800 Series': 'https://www.paloaltonetworks.com/resources/datasheets/pa-800-series-specsheet',
    'PA-1400 Series': 'https://www.paloaltonetworks.com/resources/datasheets/pa-1400-series',
    'PA-3400 Series': 'https://www.paloaltonetworks.com/resources/datasheets/pa-3400-series',
    'PA-5400 Series': 'https://www.paloaltonetworks.com/resources/datasheets/pa-5400-series',
    'PA-7000 Series': 'https://www.paloaltonetworks.com/resources/datasheets/pa-7000-series',
    'VM-Series': 'https://www.paloaltonetworks.com/resources/datasheets/vm-series-specsheet',
    'SD-WAN': 'https://www.paloaltonetworks.com/resources/datasheets/sd-wan',
    'Product Selection': 'https://www.paloaltonetworks.com/products/product-selection',
}


def _ensure_dirs():
    os.makedirs(PDF_DIR, exist_ok=True)


def _safe_filename(url):
    """Derive a safe local filename from a URL."""
    parsed = urlparse(url)
    name = parsed.path.rstrip('/').split('/')[-1]
    if not name:
        name = parsed.netloc.replace('.', '_')
    if not name.endswith('.pdf'):
        name += '.pdf'
    return name


def fetch_url(url, dest_dir=None):
    """Download a URL (PDF or HTML page) and save locally.
    Returns the local file path, or None on failure."""
    dest_dir = dest_dir or PDF_DIR
    _ensure_dirs()

    filename = _safe_filename(url)
    dest_path = os.path.join(dest_dir, filename)

    try:
        resp = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; PAN-OS-Config-Analyzer/1.0)',
        })
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', '')

        if 'application/pdf' in content_type:
            with open(dest_path, 'wb') as f:
                f.write(resp.content)
            logger.info("Downloaded PDF: %s -> %s", url, dest_path)
            return dest_path

        # If it's an HTML page (datasheet landing page), save as .html
        if 'text/html' in content_type:
            html_path = dest_path.replace('.pdf', '.html')
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(resp.text)
            logger.info("Downloaded HTML page: %s -> %s", url, html_path)
            return html_path

        # Other content — save as-is
        with open(dest_path, 'wb') as f:
            f.write(resp.content)
        logger.info("Downloaded file: %s -> %s", url, dest_path)
        return dest_path

    except Exception as e:
        logger.warning("Failed to fetch %s: %s", url, e)
        return None


def fetch_all_datasheets(dest_dir=None):
    """Fetch all known datasheet URLs. Returns dict of {series: local_path}."""
    dest_dir = dest_dir or PDF_DIR
    results = {}
    for series, url in DATASHEET_URLS.items():
        path = fetch_url(url, dest_dir)
        if path:
            results[series] = path
    logger.info("Fetched %d/%d datasheets", len(results), len(DATASHEET_URLS))
    return results


def search_web(query, max_results=3):
    """Search the web for PA documentation using DuckDuckGo (no API key).
    Returns list of {title, url, snippet}."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = []
            for r in ddgs.text(
                f"{query} site:paloaltonetworks.com datasheet",
                max_results=max_results,
            ):
                results.append({
                    'title': r.get('title', ''),
                    'url': r.get('href', ''),
                    'snippet': r.get('body', ''),
                })
            return results
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return []
