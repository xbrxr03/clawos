# SPDX-License-Identifier: AGPL-3.0-or-later
"""
Kizuna Service (braind) — Living knowledge graph for ClawOS.
絆 (Kizuna) — the bonds and ties that connect things.

Ingests documents (ZIP of PDFs, DOCX, MD, code) → extracts triples →
builds 3D knowledge graph with community detection and PageRank.
Agents read from and write back to the graph.
"""
import asyncio
import logging
import threading
import time
from pathlib import Path
from typing import Optional

log = logging.getLogger("braind")


class BrainService:
    """
    Central coordinator for the Kizuna knowledge graph.
    """

    def __init__(self):
        from services.braind.graph_builder import BrainGraph
        from services.braind.storage import get_storage

        self._graph = BrainGraph()
        self._storage = get_storage()
        self._ingesting = False
        self._ingestion_progress: dict = {}
        self._ws_callbacks: list = []  # WebSocket progress callbacks
        self._lock = threading.Lock()

        # Load persisted graph on startup
        self._load_persisted()

    def _load_persisted(self):
        """Restore graph from disk on startup."""
        try:
            data = self._storage.load_graph()
            if data.get("nodes"):
                # Rebuild NetworkX graph from saved render dict
                from services.braind.graph_builder import _node_id
                for node in data.get("nodes", []):
                    nid = node["id"]
                    if self._graph.g is not None:
                        self._graph.g.add_node(
                            nid,
                            label=node.get("label", nid),
                            sources=node.get("sources", []),
                            agent_added=node.get("agent_added", False),
                            mention_count=node.get("mention_count", 1),
                        )
                for link in data.get("links", []):
                    if self._graph.g is not None:
                        self._graph.g.add_edge(
                            link["source"], link["target"],
                            predicate=link.get("predicate", "relates_to"),
                            agent_added=link.get("agent_added", False),
                        )
                # Restore community/pagerank metadata
                self._graph._community_map = {
                    n["id"]: n.get("community", 0) for n in data.get("nodes", [])
                }
                self._graph._pagerank = {
                    n["id"]: n.get("pagerank", 0.01) for n in data.get("nodes", [])
                }
                stats = self._graph.stats()
                log.info(f"Kizuna loaded: {stats['node_count']} nodes, {stats['edge_count']} edges, {stats['community_count']} communities")
        except (OSError, ValueError) as e:
            log.warning(f"Could not load persisted graph: {e}")

    # ── WebSocket progress ─────────────────────────────────────────────────────

    def register_ws_callback(self, cb):
        self._ws_callbacks.append(cb)

    def unregister_ws_callback(self, cb):
        self._ws_callbacks = [c for c in self._ws_callbacks if c is not cb]

    def _emit_progress(self, event: str, data: dict):
        """Emit progress to all registered WebSocket listeners."""
        self._ingestion_progress = {**data, "event": event}
        for cb in list(self._ws_callbacks):
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(event, data))
                else:
                    cb(event, data)
            except (OSError, RuntimeError, AttributeError) as e:
                log.debug(f"unexpected: {e}")
                pass

    # ── ZIP ingestion ──────────────────────────────────────────────────────────

    async def ingest_zip(self, zip_path: Path) -> dict:
        """
        Full ingestion pipeline. Async — yields progress via WebSocket callbacks.
        Returns {ok, nodes_added, edges_added, files_processed, error}
        """
        if self._ingesting:
            return {"ok": False, "error": "Ingestion already in progress"}

        self._ingesting = True
        self._emit_progress("start", {"status": "starting", "message": "Reading ZIP..."})

        nodes_before = self._graph.stats()["node_count"]
        edges_before = self._graph.stats()["edge_count"]
        files_processed = 0
        total_chunks = 0
        total_triples = 0

        try:
            from services.braind.extractors import iter_zip_chunks, count_extractable

            # Count files for progress
            total_files = count_extractable(zip_path)
            self._emit_progress("count", {"total_files": total_files, "status": "extracting"})

            current_file = ""
            chunk_buffer = []

            # Stream chunks from ZIP
            for chunk in iter_zip_chunks(zip_path):
                filename = chunk["filename"]

                if filename != current_file:
                    if chunk_buffer:
                        triples = await self._process_chunk_batch(chunk_buffer, current_file)
                        total_triples += triples
                        total_chunks += len(chunk_buffer)
                        chunk_buffer = []

                    current_file = filename
                    files_processed += 1
                    self._emit_progress("file", {
                        "filename": filename,
                        "file_number": files_processed,
                        "total_files": total_files,
                        "nodes_so_far": self._graph.stats()["node_count"],
                        "status": "processing",
                    })

                chunk_buffer.append(chunk)
                await asyncio.sleep(0)  # Yield control

            # Process remaining buffer
            if chunk_buffer:
                triples = await self._process_chunk_batch(chunk_buffer, current_file)
                total_triples += triples
                total_chunks += len(chunk_buffer)

            # Recompute communities and PageRank
            self._emit_progress("computing", {"status": "computing_graph", "message": "Building connections..."})
            await asyncio.to_thread(self._graph.recompute)

            # Save to disk
            self._emit_progress("saving", {"status": "saving", "message": "Saving brain..."})
            graph_data = self._graph.to_render_dict()
            await asyncio.to_thread(self._storage.save_graph, graph_data)

            stats = self._graph.stats()
            nodes_added = stats["node_count"] - nodes_before
            edges_added = stats["edge_count"] - edges_before

            self._emit_progress("complete", {
                "status": "complete",
                "nodes_added": nodes_added,
                "edges_added": edges_added,
                "files_processed": files_processed,
                "communities": stats["community_count"],
                "message": f"Brain updated: +{nodes_added} nodes, +{edges_added} connections",
            })

            log.info(f"Kizuna ingestion complete: +{nodes_added} nodes, +{edges_added} edges from {files_processed} files")
            return {
                "ok": True,
                "nodes_added": nodes_added,
                "edges_added": edges_added,
                "files_processed": files_processed,
                "total_chunks": total_chunks,
                "total_triples": total_triples,
                "error": "",
            }

        except (ImportError, ModuleNotFoundError) as e:
            log.error(f"Brain ingestion failed: {e}")
            self._emit_progress("error", {"status": "error", "message": str(e)})
            return {"ok": False, "error": str(e)}
        finally:
            self._ingesting = False

    async def _process_chunk_batch(self, chunks: list[dict], filename: str) -> int:
        """Extract triples from a batch of chunks. Returns triple count."""
        from services.braind.graph_builder import extract_triples_llm, extract_triples_heuristic

        total_triples = 0
        for chunk in chunks:
            content = chunk.get("content", "")
            file_type = chunk.get("file_type", "text")

            # Use LLM for prose, heuristic for code
            if file_type in ("code",):
                triples = await asyncio.to_thread(extract_triples_heuristic, content, filename)
            else:
                triples = await asyncio.to_thread(extract_triples_llm, content, filename)

            if triples:
                self._graph.add_triples(triples, agent_added=False)
                total_triples += len(triples)

        self._storage.log_ingestion(filename, len(chunks), total_triples)
        return total_triples

    # ── Agent expand ──────────────────────────────────────────────────────────

    async def expand_from_agent(self, text: str, source: str = "agent",
                                 task_id: str = "") -> dict:
        """
        Called by agents after task completion.
        Runs significance filter — only adds genuinely new knowledge.
        Returns {added: bool, nodes_added: int, reason: str}
        """
        from services.braind.significance_filter import is_significant
        from services.braind.graph_builder import extract_triples_llm

        should_add, score, reason = is_significant(text)
        if not should_add:
            log.debug(f"Brain expand skipped: {reason} (score={score:.2f})")
            return {"added": False, "nodes_added": 0, "reason": reason}

        before = self._graph.stats()["node_count"]
        triples = await asyncio.to_thread(extract_triples_llm, text, source)

        if triples:
            self._graph.add_triples(triples, agent_added=True)
            # Incremental recompute (lightweight)
            await asyncio.to_thread(self._graph.recompute)
            # Save
            graph_data = self._graph.to_render_dict()
            await asyncio.to_thread(self._storage.save_graph, graph_data)

        added = self._graph.stats()["node_count"] - before
        log.info(f"Brain expand: +{added} nodes from agent (score={score:.2f}, task={task_id})")
        return {
            "added": added > 0,
            "nodes_added": added,
            "triples_extracted": len(triples),
            "reason": reason,
            "significance_score": round(score, 3),
        }

    # ── GraphRAG context ──────────────────────────────────────────────────────

    def get_context(self, query: str, top_n: int = 8) -> dict:
        """
        GraphRAG retrieval for agents.
        Finds relevant nodes via label matching, then expands 2 hops.
        Returns {nodes: [...], context_text: str}
        """
        # Find seed nodes matching query
        matching = self._storage.search_nodes(query, limit=top_n)
        seed_ids = [n["id"] for n in matching]

        # Graph neighborhood expansion
        neighborhood_labels = self._graph.graph_rag_context(seed_ids, hops=2)

        # Combine
        all_labels = list({n["label"] for n in matching} | set(neighborhood_labels))

        context_text = ""
        if all_labels:
            context_text = (
                f"[Kizuna Context — related knowledge]\n"
                + "\n".join(f"• {label}" for label in all_labels[:20])
                + "\n[End Brain Context]"
            )

        return {
            "nodes": matching,
            "neighborhood_labels": neighborhood_labels[:20],
            "context_text": context_text,
        }

    # ── Graph data for frontend ───────────────────────────────────────────────

    def get_graph(self) -> dict:
        return self._graph.to_render_dict()

    def get_node(self, node_id: str) -> Optional[dict]:
        return self._graph.node_detail(node_id)

    def get_gaps(self) -> list[dict]:
        from services.braind.gaps import find_gaps
        return find_gaps(self._graph)

    def get_status(self) -> dict:
        stats = self._graph.stats()
        return {
            **stats,
            "ingesting": self._ingesting,
            "progress": self._ingestion_progress,
        }

    def stats(self) -> dict:
        return {**self._graph.stats(), "ingesting": self._ingesting}


# ── Singleton ──────────────────────────────────────────────────────────────────
_brain: Optional[BrainService] = None


def get_brain() -> BrainService:
    global _brain
    if _brain is None:
        _brain = BrainService()
    return _brain
