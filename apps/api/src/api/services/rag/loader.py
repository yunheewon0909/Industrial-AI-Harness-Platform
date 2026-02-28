from __future__ import annotations

import hashlib
from pathlib import Path

from api.services.rag.types import SourceDocument

SUPPORTED_EXTENSIONS = {".txt", ".md"}


def load_documents(
    source_dir: Path,
    supported_extensions: set[str] | None = None,
) -> list[SourceDocument]:
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    extensions = supported_extensions or SUPPORTED_EXTENSIONS
    files = sorted(
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in extensions
    )

    documents: list[SourceDocument] = []
    for path in files:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue

        relative_path = path.relative_to(source_dir).as_posix()
        doc_id = hashlib.sha256(relative_path.encode("utf-8")).hexdigest()[:16]
        documents.append(
            SourceDocument(
                doc_id=doc_id,
                source_path=relative_path,
                text=text,
            )
        )

    if not documents:
        raise ValueError(
            f"No non-empty supported documents found in {source_dir} "
            f"(supported: {sorted(extensions)})"
        )

    return documents
