"""Compatibility interface for explicit local extraction; no implicit uploads."""
from .retrieval import make_chunks, retrieve


class LocalSourceParser:
    def extract_knowledge(self):
        if not self.path.exists():
            self.knowledge_cache = {}
            return {}
        self.records = make_chunks(self.path, self.path.name, "confidential")
        self.knowledge_cache = {record["location"]: record["text"] for record in self.records}
        return self.knowledge_cache

    def search_knowledge(self, query):
        if not self.knowledge_cache:
            self.extract_knowledge()
        records = retrieve(self.records, query, 12000)
        return [{"section": r["location"], "content": r["text"], "source_id": r["id"], "sha256": r["sha256"]} for r in records]

    def get_relevant_context(self, process_name):
        return "\n\n".join(f"[{r['source_id']}] {r['section']}\n{r['content']}" for r in self.search_knowledge(process_name))
