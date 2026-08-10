"""Index the knowledge base into the vector store for Agent 3.

    python -m scripts.seed_knowledge_base
    python -m scripts.seed_knowledge_base --query "can a bank ask for my OTP?"

Re-running is safe: the collection is rebuilt from the markdown on disk, so
edited or deleted documents do not leave stale chunks behind.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.ml.rag.retriever import KnowledgeRetriever  # noqa: E402


def main() -> int:
    settings = get_settings()
    configure_logging(settings)

    parser = argparse.ArgumentParser(description="Seed the ScamShield knowledge base")
    parser.add_argument(
        "--query", type=str, default=None, help="Run a test retrieval after indexing."
    )
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    retriever = KnowledgeRetriever(settings)
    count = retriever.ensure_indexed_sync(force=True)

    info = retriever.describe()
    print(f"Indexed {count} chunks from {settings.resolve(settings.knowledge_base_path)}")
    print(f"Store   : {info['store']}")
    print(f"Embedder: {info['embedding_model']}")

    if count == 0:
        print("\nNo chunks indexed — check that the knowledge base directory has .md files.")
        return 1

    if args.query:
        print(f"\n=== Retrieval for: {args.query!r} ===")
        for document in retriever.store.search(args.query, top_k=args.top_k):
            print(f"\n[{document.score:.3f}] {document.title}  ({document.source})")
            print(document.content[:300].strip() + ("…" if len(document.content) > 300 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
