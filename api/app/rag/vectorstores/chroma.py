import chromadb
from chromadb.errors import NotFoundError

from app.rag.vectorstores.base import VectorHit, VectorStore


class ChromaVectorStore(VectorStore):
    """Adapter over Chroma's HTTP client. Each namespace is a collection with an HNSW cosine index."""

    def __init__(self, host: str, port: int):
        self.client = chromadb.HttpClient(host=host, port=port)

    def _collection(self, namespace: str):
        return self.client.get_or_create_collection(namespace, metadata={"hnsw:space": "cosine"})

    def upsert(self, namespace, ids, embeddings, documents, metadatas) -> None:
        if ids:
            self._collection(namespace).upsert(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )

    def query(self, namespace: str, embedding: list[float], k: int) -> list[VectorHit]:
        try:
            col = self.client.get_collection(namespace)
        except NotFoundError:
            return []  # bot has no documents yet
        count = col.count()
        if count == 0:
            return []
        res = col.query(query_embeddings=[embedding], n_results=min(k, count), include=["distances"])
        # Chroma returns cosine *distance*; similarity = 1 - distance.
        return [VectorHit(cid, 1.0 - dist) for cid, dist in zip(res["ids"][0], res["distances"][0])]

    def delete_document(self, namespace: str, document_id: str) -> None:
        try:
            self.client.get_collection(namespace).delete(where={"document_id": document_id})
        except NotFoundError:
            pass

    def drop_namespace(self, namespace: str) -> None:
        try:
            self.client.delete_collection(namespace)
        except NotFoundError:
            pass

    def ping(self) -> bool:
        try:
            self.client.heartbeat()
            return True
        except Exception:
            return False
