from __future__ import annotations

import argparse
from pathlib import Path
import sys

from api.config import get_settings
from api.services.rag import ingest_documents


def _build_parser() -> argparse.ArgumentParser:
    settings = get_settings()

    parser = argparse.ArgumentParser(
        prog="rag-ingest",
        description="Ingest sample docs and persist a local RAG index",
    )
    parser.add_argument(
        "--source-dir",
        default=settings.rag_source_dir,
        help="Source directory containing .txt/.md documents",
    )
    parser.add_argument(
        "--index-dir",
        default=settings.rag_index_dir,
        help="Output directory for persisted index artifacts",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=settings.rag_chunk_size,
        help="Chunk size in characters",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=settings.rag_chunk_overlap,
        help="Chunk overlap in characters",
    )
    parser.add_argument(
        "--embedding-dim",
        type=int,
        default=settings.rag_embedding_dim,
        help="Deterministic embedding dimension",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        summary = ingest_documents(
            source_dir=Path(args.source_dir),
            output_dir=Path(args.index_dir),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            embedding_dim=args.embedding_dim,
        )
    except Exception as exc:
        print(f"[rag-ingest] failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc

    print(
        "[rag-ingest] completed "
        f"documents={summary.document_count} "
        f"chunks={summary.chunk_count} "
        f"index={summary.index_file}",
        flush=True,
    )


if __name__ == "__main__":
    main()
