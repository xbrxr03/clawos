"""clawctl project — document ingestion and RAG pipeline."""
import sys
from pathlib import Path
from clawctl.ui.banner import success, error, info, table


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

    # Copy into workspace
    from clawos_core.constants import WORKSPACE_DIR
    ws_dir = WORKSPACE_DIR / workspace
    ws_dir.mkdir(parents=True, exist_ok=True)
    dest = ws_dir / src.name
    import shutil
    shutil.copy2(src, dest)
    info(f"Copied {src.name} → workspace/{workspace}/")

    # Ingest via ragd
    info("Indexing document (this may take 30–60s for large files)...")
    try:
        from clawos_core.util.paths import workspace_path
        from services.ragd.service import get_rag
        ws_root = workspace_path(workspace)
        rag = get_rag(workspace, ws_root)
        result = rag.ingest(dest)
        chunks = result.get("chunks", "?")
        success(f"Indexed {src.name} — {chunks} chunks ready for RAG")
    except Exception as e:
        error(f"Ingestion failed: {e}")
        info("File was copied to workspace. Try: systemctl --user restart clawos")
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
        rows = [(d["title"], d["type"], str(d["chunks"]), d["added"][:10]) for d in docs]
        table(rows, headers=("document", "type", "chunks", "added"))
    except Exception as e:
        error(f"Could not list documents: {e}")
    print()


def run_query(question: str, workspace: str = "nexus_default"):
    print()
    if not question:
        error("Usage: clawctl project query '<question>'")
        return
    try:
        from clawos_core.util.paths import workspace_path
        from services.ragd.service import get_rag
        ws_root = workspace_path(workspace)
        rag = get_rag(workspace, ws_root)
        result = rag.answer(question)
        answer = result.get("answer", "[no answer]")
        trust  = result.get("trust_label", "")
        sources = result.get("sources", [])
        print(f"\n  {answer}\n")
        if sources:
            print(f"  Sources:")
            for s in sources:
                print(f"    {s['ref']} {s['title']} p.{s['page']}")
        print(f"\n  [{trust}]\n")
    except Exception as e:
        error(f"Query failed: {e}")
    print()


def run_stats(workspace: str = "nexus_default"):
    print()
    try:
        from clawos_core.util.paths import workspace_path
        from services.ragd.service import get_rag
        ws_root = workspace_path(workspace)
        rag = get_rag(workspace, ws_root)
        s = rag.stats()
        print(f"  Workspace:  {s['workspace']}")
        print(f"  Documents:  {s['documents']}")
        print(f"  Chunks:     {s['chunks']}")
        print(f"  Vectors:    {s['vectors']}")
        print(f"  Embed model:{s['embed_model']}")
    except Exception as e:
        error(f"Stats unavailable: {e}")
    print()
