from __future__ import annotations

import argparse
from pathlib import Path
import sys

from api.config import get_settings
from api.services.rag.reindex_job_runner import run_reindex_job


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
        "--db-path",
        default=settings.rag_db_path,
        help="Output sqlite DB path for persisted index artifacts",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    try:
        metrics = run_reindex_job(
            source_dir=Path(args.source_dir),
            db_path=Path(args.db_path),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    except Exception as exc:
        print(f"[rag-ingest] failed: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1) from exc

    print(
        "[rag-ingest] completed "
        f"documents={metrics['documents']} "
        f"chunks={metrics['chunks']} "
        f"db_path={metrics['db_path']}",
        flush=True,
    )


if __name__ == "__main__":
    main()
