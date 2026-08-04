"""ChromaDB local vector store for PA datasheet embeddings."""

import os
import logging

import chromadb

logger = logging.getLogger(__name__)

RAG_DATA_DIR = os.environ.get('RAG_DATA_DIR', '/app/rag_data')
CHROMA_DIR = os.path.join(RAG_DATA_DIR, 'chroma')
COLLECTION_NAME = 'panos_datasheets'

_client = None
_collection = None


def _ensure_dirs():
    os.makedirs(CHROMA_DIR, exist_ok=True)


def get_client():
    """Return a persistent ChromaDB client (singleton)."""
    global _client
    if _client is None:
        _ensure_dirs()
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        logger.info("ChromaDB client initialized at %s", CHROMA_DIR)
    return _client


def get_collection():
    """Return the datasheets collection, creating it if needed.
    Uses ChromaDB's default ONNX embedding function (all-MiniLM-L6-v2)."""
    global _collection
    if _collection is None:
        client = get_client()
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"description": "Palo Alto Networks product datasheets"},
        )
        logger.info("Collection '%s' ready (%d documents)",
                     COLLECTION_NAME, _collection.count())
    return _collection


def is_initialized():
    """Check if the collection has any documents."""
    try:
        return get_collection().count() > 0
    except Exception:
        return False


def reset_collection():
    """Delete and recreate the collection (for full re-ingest)."""
    global _collection
    client = get_client()
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = None
    return get_collection()
