"""clawctl project — document ingestion and RAG pipeline."""
from pathlib import Path

from clawctl.ui.banner import error, info, success, table
from clawos_core.service_manager import service_hint


def run_upload(filepath: str, workspace: str = "nexus_default"):
    print()
    src = Path(filepath).expanduser().resolve()
    if not src.exists():
        error(f"File not found: {filepath}")
        return

    supported = {".pdf", ".txt", ".md", ".docx"}
    if src.suffix.lower() not in supported:
        error(f"Unsupported file type: {src.suffix}  (supported: pdf txt md docx)")
        return

    from clawos_core.constants import WORKSPACE_DIR
    import shutil

    ws_dir = WORKSPACE_DIR / workspace
    ws_dir.mkdir(parents=True, exist_ok=True)
    dest = ws_dir / src.name
    shutil.copy2(src, dest)
    info(f"Copied {src.name} → workspace/{workspace}/")

    info("Indexing document (this may take 30–60s for large files)...")
    try:
        from clawos_core.util.paths import workspace_path
        from services.ragd.service import get_rag

        ws_root = workspace_path(workspace)
        rag = get_rag(workspace, ws_root)
        result = rag.ingest(dest)
        chunks = result.get("chunks", "?")
        success(f"Indexed {src.name} — {chunks} chunks ready for RAG")
    except Exception as exc:
        error(f"Ingestion failed: {exc}")
        info(f"File was copied to workspace. Try: {service_hint('restart', 'clawos.service')}")
    print()


def run_list(workspace: str = "nexus_default"):
    print()
    try:
        from clawos_core.util.paths import workspace_path
        from services.ragd.service import get_rag

        ws_root = workspace_path(workspace)
        rag = get_rag(workspace, ws_root)
        docs = rag.list_files()
        if not docs:
            info(f"No documents indexed in workspace: {workspace}")
            info("Upload one: clawctl project upload <file>")
            return
        rows = [(doc["title"], doc["type"], str(doc["chunks"]), doc["added"][:10]) for doc in docs]
        table(rows, headers=("document", "type", "chunks", "added"))
    except Exception as exc:
        error(f"Could not list documents: {exc}")
    print()


def run_query(question: str, workspace: str = "nexus_default"):
    print()
    if not question:
        error("Usage: clawctl project query '<question>'")
        return
    try:
        from clawos_core.util.paths import workspace_path
        from services.ragd.service import RAGService

        ws_root = workspace_path(workspace)
        rag = RAGService(workspace, ws_root)
        result = rag.answer(question)
        answer = result.get("answer", "[no answer]")
        trust = result.get("trust_label", "")
        sources = result.get("sources", [])
        print(f"\n  {answer}\n")
        if sources:
            print("  Sources:")
            for source in sources:
                print(f"    {source['ref']} {source['title']} p.{source['page']}")
        print(f"\n  [{trust}]\n")
    except Exception as exc:
        error(f"Query failed: {exc}")
    print()


def run_stats(workspace: str = "nexus_default"):
    print()
    try:
        from clawos_core.util.paths import workspace_path
        from services.ragd.service import get_rag

        ws_root = workspace_path(workspace)
        rag = get_rag(workspace, ws_root)
        stats = rag.stats()
        print(f"  Workspace:  {stats['workspace']}")
        print(f"  Documents:  {stats['documents']}")
        print(f"  Chunks:     {stats['chunks']}")
        print(f"  Vectors:    {stats['vectors']}")
        print(f"  Embed model:{stats['embed_model']}")
    except Exception as exc:
        error(f"Stats unavailable: {exc}")
    print()
