"""PDF and HTML parsing, chunking, and embedding into ChromaDB."""

import hashlib
import logging
import os
import re

logger = logging.getLogger(__name__)

# Model name patterns to detect in text chunks
_MODEL_PATTERN = re.compile(
    r'\b(PA-\d{3,4}[A-Z]?|VM-\d{2,4}(?:-HV)?)\b', re.IGNORECASE
)


def _extract_text_from_pdf(pdf_path):
    """Extract text from a PDF file, returning list of (page_num, text)."""
    import pdfplumber
    pages = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ''
                # Also try extracting tables as text
                tables = page.extract_tables() or []
                for table in tables:
                    for row in table:
                        if row:
                            cells = [str(c) for c in row if c]
                            if cells:
                                text += '\n' + ' | '.join(cells)
                if text.strip():
                    pages.append((i + 1, text.strip()))
    except Exception as e:
        logger.warning("Failed to parse PDF %s: %s", pdf_path, e)
    return pages


def _extract_text_from_html(html_path):
    """Extract text from an HTML file, returning list of (section_num, text)."""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Strip HTML tags for a simple text extraction
        text = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if not text:
            return []

        # Split into chunks of ~1000 chars at sentence boundaries
        chunks = []
        words = text.split()
        current = []
        current_len = 0
        section = 1
        for word in words:
            current.append(word)
            current_len += len(word) + 1
            if current_len >= 1000 and word.endswith(('.', ':', ';')):
                chunks.append((section, ' '.join(current)))
                current = []
                current_len = 0
                section += 1
        if current:
            chunks.append((section, ' '.join(current)))
        return chunks

    except Exception as e:
        logger.warning("Failed to parse HTML %s: %s", html_path, e)
        return []


def _detect_model_names(text):
    """Find all PA/VM model names mentioned in a text chunk."""
    matches = _MODEL_PATTERN.findall(text)
    return list(set(m.upper() for m in matches))


def _chunk_id(source_url, page_num, chunk_idx):
    """Generate a deterministic chunk ID for deduplication."""
    raw = f"{source_url}::{page_num}::{chunk_idx}"
    return hashlib.md5(raw.encode()).hexdigest()


def _split_page_into_chunks(text, max_chars=800):
    """Split a page's text into smaller chunks at paragraph boundaries."""
    paragraphs = re.split(r'\n{2,}', text)
    chunks = []
    current = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current_len + len(para) > max_chars and current:
            chunks.append('\n'.join(current))
            current = [para]
            current_len = len(para)
        else:
            current.append(para)
            current_len += len(para)

    if current:
        chunks.append('\n'.join(current))

    return chunks if chunks else [text]


def ingest_file(file_path, source_url='', collection=None):
    """Parse a PDF or HTML file and embed chunks into ChromaDB.
    Returns the number of chunks ingested."""
    if collection is None:
        from sizing.rag.store import get_collection
        collection = get_collection()

    source_file = os.path.basename(file_path)

    # Check if already ingested (by source_url)
    if source_url:
        existing = collection.get(where={"source_url": source_url})
        if existing and existing['ids']:
            logger.info("Already ingested %s (%d chunks), skipping",
                        source_file, len(existing['ids']))
            return 0

    # Extract text based on file type
    if file_path.endswith('.pdf'):
        pages = _extract_text_from_pdf(file_path)
    elif file_path.endswith('.html'):
        pages = _extract_text_from_html(file_path)
    else:
        logger.warning("Unsupported file type: %s", file_path)
        return 0

    if not pages:
        logger.warning("No text extracted from %s", file_path)
        return 0

    ids = []
    documents = []
    metadatas = []

    for page_num, page_text in pages:
        chunks = _split_page_into_chunks(page_text)
        for chunk_idx, chunk_text in enumerate(chunks):
            if len(chunk_text.strip()) < 50:
                continue  # Skip tiny chunks

            model_names = _detect_model_names(chunk_text)
            doc_id = _chunk_id(source_url or file_path, page_num, chunk_idx)

            ids.append(doc_id)
            documents.append(chunk_text)
            metadatas.append({
                'source_url': source_url or '',
                'source_file': source_file,
                'page_number': page_num,
                'model_names': ','.join(model_names) if model_names else '',
                'chunk_index': chunk_idx,
            })

    if not ids:
        return 0

    # Batch add to ChromaDB (max 5000 per batch)
    batch_size = 5000
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i:i + batch_size],
            documents=documents[i:i + batch_size],
            metadatas=metadatas[i:i + batch_size],
        )

    logger.info("Ingested %s: %d chunks", source_file, len(ids))
    return len(ids)


def ingest_all(data_dir=None):
    """Fetch all known datasheets and ingest them.
    Returns total number of chunks ingested."""
    from sizing.rag.sources import fetch_all_datasheets, DATASHEET_URLS, PDF_DIR

    data_dir = data_dir or PDF_DIR
    fetched = fetch_all_datasheets(data_dir)

    from sizing.rag.store import get_collection
    collection = get_collection()

    total = 0
    for series, local_path in fetched.items():
        source_url = DATASHEET_URLS.get(series, '')
        count = ingest_file(local_path, source_url=source_url, collection=collection)
        total += count

    logger.info("Total chunks ingested: %d", total)
    return total


def remove_source(source_url):
    """Remove all chunks from a specific source URL."""
    from sizing.rag.store import get_collection
    collection = get_collection()
    existing = collection.get(where={"source_url": source_url})
    if existing and existing['ids']:
        collection.delete(ids=existing['ids'])
        logger.info("Removed %d chunks for %s", len(existing['ids']), source_url)
        return len(existing['ids'])
    return 0
