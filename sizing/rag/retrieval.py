"""Query ChromaDB for relevant documentation snippets."""

import logging

logger = logging.getLogger(__name__)


def get_model_docs(model_name, n_results=5):
    """Query ChromaDB for chunks relevant to a specific PA/VM model.
    Returns list of {text, source_url, source_file, page, score}."""
    try:
        from sizing.rag.store import get_collection, is_initialized
        if not is_initialized():
            return []

        collection = get_collection()

        # Query by model name text + metadata filter
        results = collection.query(
            query_texts=[f"{model_name} specifications throughput performance"],
            n_results=n_results,
            where={"model_names": {"$contains": model_name.upper()}},
        )

        docs = _format_results(results)

        # If metadata filter returned nothing, try text-only query
        if not docs:
            results = collection.query(
                query_texts=[f"{model_name} specifications throughput sessions tunnels"],
                n_results=n_results,
            )
            docs = _format_results(results)

        return docs

    except Exception as e:
        logger.warning("ChromaDB query failed for %s: %s", model_name, e)
        return []


def search_and_retrieve(model_name, n_results=5):
    """Get docs for a model, falling back to web search if nothing found locally."""
    docs = get_model_docs(model_name, n_results)
    if docs:
        return docs

    # Web search fallback
    try:
        from sizing.rag.sources import search_web, fetch_url
        from sizing.rag.ingest import ingest_file

        logger.info("No local docs for %s, trying web search", model_name)
        search_results = search_web(f"Palo Alto {model_name} datasheet specifications")

        for result in search_results:
            url = result.get('url', '')
            if not url:
                continue
            local_path = fetch_url(url)
            if local_path:
                ingest_file(local_path, source_url=url)

        # Re-query after ingesting new docs
        return get_model_docs(model_name, n_results)

    except Exception as e:
        logger.warning("Web search fallback failed for %s: %s", model_name, e)
        return []


def get_docs_for_sizing_result(sizing_result):
    """Given a full sizing result dict, retrieve relevant docs for all recommended models.
    Returns dict of {role: [doc_snippets]}."""
    doc_refs = {}

    for role_key in ('hub', 'branch', 'hub_virtual'):
        role_data = sizing_result.get(role_key)
        if not role_data:
            continue
        model_name = role_data.get('model', '')
        if not model_name:
            continue

        docs = search_and_retrieve(model_name, n_results=3)
        if docs:
            doc_refs[role_key] = docs

    # Hub options: retrieve docs for each per-series recommendation
    seen_models = {sizing_result.get('hub', {}).get('model', '')}
    for i, opt in enumerate(sizing_result.get('hub_options', [])):
        model_name = opt.get('model', '')
        if not model_name or model_name in seen_models:
            continue
        seen_models.add(model_name)
        docs = search_and_retrieve(model_name, n_results=3)
        if docs:
            doc_refs[f'hub_option_{i + 1}'] = docs

    # Branch options: retrieve docs for each per-series recommendation
    seen_models.add(sizing_result.get('branch', {}).get('model', ''))
    for i, opt in enumerate(sizing_result.get('branch_options', [])):
        model_name = opt.get('model', '')
        if not model_name or model_name in seen_models:
            continue
        seen_models.add(model_name)
        docs = search_and_retrieve(model_name, n_results=3)
        if docs:
            doc_refs[f'branch_option_{i + 1}'] = docs

    return doc_refs


def _format_results(results):
    """Convert ChromaDB query results to a clean list of dicts."""
    if not results or not results.get('documents'):
        return []

    docs = []
    documents = results['documents'][0] if results['documents'] else []
    metadatas = results['metadatas'][0] if results.get('metadatas') else [{}] * len(documents)
    distances = results['distances'][0] if results.get('distances') else [0] * len(documents)

    for doc, meta, dist in zip(documents, metadatas, distances):
        if not doc or not doc.strip():
            continue
        docs.append({
            'text': doc.strip(),
            'source_url': meta.get('source_url', ''),
            'source_file': meta.get('source_file', ''),
            'page': meta.get('page_number', 0),
            'score': round(1 - dist, 3) if dist else 0,
        })

    return docs
