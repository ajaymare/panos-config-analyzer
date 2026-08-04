"""Auto-refresh logic for datasheet ingestion."""

import json
import logging
import os
import time
from datetime import datetime

logger = logging.getLogger(__name__)

RAG_DATA_DIR = os.environ.get('RAG_DATA_DIR', '/app/rag_data')
METADATA_FILE = os.path.join(RAG_DATA_DIR, 'metadata.json')


def _load_metadata():
    """Load refresh metadata from disk."""
    try:
        if os.path.exists(METADATA_FILE):
            with open(METADATA_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        logger.warning("Failed to load metadata: %s", e)
    return {}


def _save_metadata(meta):
    """Save refresh metadata to disk."""
    os.makedirs(RAG_DATA_DIR, exist_ok=True)
    try:
        with open(METADATA_FILE, 'w') as f:
            json.dump(meta, f, indent=2)
    except Exception as e:
        logger.warning("Failed to save metadata: %s", e)


def refresh_datasheets():
    """Re-fetch all known datasheets and re-ingest changed ones.
    Returns summary dict."""
    from sizing.rag.store import reset_collection
    from sizing.rag.ingest import ingest_all

    logger.info("Starting full datasheet refresh...")

    # Reset collection for clean re-ingest
    reset_collection()
    total_chunks = ingest_all()

    meta = _load_metadata()
    meta['last_refresh'] = datetime.utcnow().isoformat()
    meta['last_refresh_chunks'] = total_chunks
    meta['refresh_count'] = meta.get('refresh_count', 0) + 1
    _save_metadata(meta)

    logger.info("Refresh complete: %d chunks ingested", total_chunks)
    return {
        'status': 'complete',
        'chunks_ingested': total_chunks,
        'timestamp': meta['last_refresh'],
    }


def auto_refresh_if_stale(max_age_days=30):
    """Refresh datasheets only if the last refresh was more than max_age_days ago.
    Returns True if a refresh was triggered."""
    meta = _load_metadata()
    last_refresh = meta.get('last_refresh')

    if last_refresh:
        try:
            last_dt = datetime.fromisoformat(last_refresh)
            age_days = (datetime.utcnow() - last_dt).days
            if age_days < max_age_days:
                logger.info("Datasheets are %d days old (max %d), skipping refresh",
                            age_days, max_age_days)
                return False
        except (ValueError, TypeError):
            pass  # Invalid date, do refresh

    logger.info("Datasheets are stale or never fetched, triggering refresh")
    refresh_datasheets()
    return True


def get_status():
    """Return current datasheet ingestion status."""
    from sizing.rag.store import is_initialized, get_collection
    from sizing.rag.sources import DATASHEET_URLS, PDF_DIR

    meta = _load_metadata()

    # Count downloaded files
    downloaded_files = []
    if os.path.exists(PDF_DIR):
        downloaded_files = [f for f in os.listdir(PDF_DIR)
                           if f.endswith(('.pdf', '.html'))]

    doc_count = 0
    if is_initialized():
        try:
            doc_count = get_collection().count()
        except Exception:
            pass

    return {
        'initialized': is_initialized(),
        'total_chunks': doc_count,
        'known_sources': len(DATASHEET_URLS),
        'downloaded_files': len(downloaded_files),
        'files': downloaded_files,
        'last_refresh': meta.get('last_refresh'),
        'refresh_count': meta.get('refresh_count', 0),
    }
