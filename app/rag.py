"""Document ingestion and retrieval for RAG."""
from pathlib import Path

from pypdf import PdfReader

from app import config, store

SYSTEM_PROMPT = (
    "You are a customer-support assistant. Answer the user's question using "
    "only the context provided. If the answer is not in the context, say you "
    "don't know rather than guessing. Keep the answer concise."
)


def build_prompt(question: str, hits: list[dict]) -> str:
    """Assemble the retrieved chunks and the question into a single prompt."""
    context = "\n\n".join(f"[{h['source']}] {h['text']}" for h in hits)
    return f"Context:\n{context}\n\nQuestion: {question}"


def _read_segments(path: Path) -> list[tuple[str, int | None]]:
    """Return (text, page) segments. PDFs are split per page; text files
    are a single segment with page=None."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return [(page.extract_text() or "", i + 1) for i, page in enumerate(reader.pages)]
    if suffix in (".md", ".txt"):
        return [(path.read_text(encoding="utf-8"), None)]
    raise ValueError(f"Unsupported file type: {path.name}")


def _chunk(text: str, size: int, overlap: int) -> list[str]:
    """Split text into overlapping character windows."""
    text = text.strip()
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += size - overlap
    return chunks


def ingest_file(path: Path) -> int:
    """Chunk a single file and add it to the vector store. Returns chunk count."""
    collection = store.get_collection()
    documents, metadatas, ids = [], [], []

    for text, page in _read_segments(path):
        for idx, chunk in enumerate(_chunk(text, config.CHUNK_SIZE, config.CHUNK_OVERLAP)):
            meta = {"source": path.name}
            if page is not None:
                meta["page"] = page
            documents.append(chunk)
            metadatas.append(meta)
            ids.append(f"{path.name}:{page}:{idx}")

    if documents:
        collection.upsert(documents=documents, metadatas=metadatas, ids=ids)
    return len(documents)


def ingest_dir(data_dir: str = "data") -> dict[str, int]:
    """Ingest every supported file in a directory. Returns {filename: chunks}."""
    counts = {}
    for path in sorted(Path(data_dir).iterdir()):
        if path.suffix.lower() in (".pdf", ".md", ".txt"):
            counts[path.name] = ingest_file(path)
    return counts


def retrieve(query: str, k: int = config.TOP_K) -> list[dict]:
    """Return the k most relevant chunks for a query, with their source info."""
    collection = store.get_collection()
    result = collection.query(query_texts=[query], n_results=k)

    hits = []
    # Chroma returns each field as a list-of-lists (one inner list per query).
    for text, meta, distance in zip(
        result["documents"][0], result["metadatas"][0], result["distances"][0]
    ):
        hits.append(
            {
                "text": text,
                "source": meta.get("source"),
                "page": meta.get("page"),
                "distance": distance,
            }
        )
    return hits
