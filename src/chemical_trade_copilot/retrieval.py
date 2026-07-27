from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

import chromadb
from langchain_text_splitters import RecursiveCharacterTextSplitter

from .embeddings import Embedder, MultilingualE5Embedder
from .pdf_pages import PageRecord


@dataclass(frozen=True, slots=True)
class SearchResult:
    text: str
    product: str
    doc_type: str
    source_file: str
    source_path: Path
    page_number: int
    distance: float


@dataclass(frozen=True, slots=True)
class _PageChunk:
    text: str
    page: PageRecord
    chunk_number: int


class PageIndex:
    def __init__(
        self,
        database_path: Path,
        *,
        embedder: Embedder | None = None,
        collection_name: str = "page_evidence",
    ) -> None:
        database_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(database_path))
        self._collection = self._client.get_or_create_collection(collection_name)
        self._embedder = embedder or MultilingualE5Embedder()
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=150,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def replace(self, pages: list[PageRecord]) -> None:
        chunks = self._chunks(pages)
        embeddings = (
            self._embedder.encode([f"passage: {chunk.text}" for chunk in chunks])
            if chunks
            else []
        )
        current = self._collection.get(include=[])["ids"]
        if current:
            self._collection.delete(ids=current)
        if not chunks:
            return
        self._collection.add(
            ids=[self._id(chunk) for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=embeddings,
            metadatas=[
                {
                    "product": chunk.page.product,
                    "doc_type": chunk.page.doc_type,
                    "source_file": chunk.page.source_file,
                    "source_path": str(chunk.page.source_path),
                    "page_number": chunk.page.page_number,
                    "chunk_number": chunk.chunk_number,
                }
                for chunk in chunks
            ],
        )

    def query(self, inquiry: str, *, limit: int = 5) -> list[SearchResult]:
        if not inquiry.strip():
            raise ValueError("Inquiry must not be empty")
        if limit < 1:
            raise ValueError("Limit must be at least 1")
        if self._collection.count() == 0:
            return []

        result = self._collection.query(
            query_embeddings=self._embedder.encode([f"query: {inquiry.strip()}"]),
            n_results=min(limit * 4, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        documents = result["documents"][0]
        metadatas = result["metadatas"][0]
        distances = result["distances"][0]
        results: list[SearchResult] = []
        seen_pages: set[tuple[str, int]] = set()
        for document, metadata, distance in zip(documents, metadatas, distances):
            page_key = (str(metadata["source_path"]), int(metadata["page_number"]))
            if page_key in seen_pages:
                continue
            seen_pages.add(page_key)
            results.append(
                SearchResult(
                    text=document,
                    product=str(metadata["product"]),
                    doc_type=str(metadata["doc_type"]),
                    source_file=str(metadata["source_file"]),
                    source_path=Path(str(metadata["source_path"])),
                    page_number=int(metadata["page_number"]),
                    distance=float(distance),
                )
            )
            if len(results) == limit:
                break
        return results

    def _chunks(self, pages: list[PageRecord]) -> list[_PageChunk]:
        return [
            _PageChunk(text=text, page=page, chunk_number=chunk_number)
            for page in pages
            for chunk_number, text in enumerate(self._splitter.split_text(page.text), start=1)
        ]

    @staticmethod
    def _id(chunk: _PageChunk) -> str:
        identity = (
            f"{chunk.page.source_path}|{chunk.page.page_number}|{chunk.chunk_number}"
        ).encode("utf-8")
        return sha256(identity).hexdigest()
