import httpx

from app.rag.embeddings.base import Embedder

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"


class VoyageEmbedder(Embedder):
    """Adapter over the Voyage AI embeddings REST API. Sends documents in batches to cut round trips."""

    def __init__(
        self,
        api_key: str,
        model: str,
        batch_size: int = 128,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("Voyage embeddings need VOYAGE_API_KEY")
        self.model = model
        self.batch_size = batch_size
        # One pooled client for connection reuse (keep-alive) across calls.
        self._client = httpx.Client(
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def _request(self, texts: list[str], input_type: str) -> list[list[float]]:
        resp = self._client.post(
            VOYAGE_URL, json={"input": texts, "model": self.model, "input_type": input_type}
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda d: d["index"])
        return [d["embedding"] for d in data]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch_size):
            out.extend(self._request(texts[i : i + self.batch_size], "document"))
        return out

    def embed_query(self, text: str) -> list[float]:
        return self._request([text], "query")[0]
