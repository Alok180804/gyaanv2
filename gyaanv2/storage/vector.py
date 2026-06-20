from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, FilterSelector

class VectorStore:
    def __init__(self, path:Path, collection:str, vector_size:int):
        self.collection=collection; self.client=QdrantClient(path=str(path))
        names=[c.name for c in self.client.get_collections().collections]
        if collection not in names:
            self.client.create_collection(collection_name=collection, vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE))
    def upsert_chunks(self, chunks, vectors):
        pts=[PointStruct(id=ch.chunk_id, vector=vec, payload={**ch.metadata,'content':ch.content}) for ch,vec in zip(chunks,vectors)]
        if pts: self.client.upsert(collection_name=self.collection, points=pts)
    def delete_document(self, document_id:int):
        self.client.delete(collection_name=self.collection, points_selector=FilterSelector(filter=Filter(must=[FieldCondition(key='document_id', match=MatchValue(value=document_id))])))
    def search(self, vector, limit:int):
        return self.client.query_points(collection_name=self.collection, query=vector, limit=limit, with_payload=True).points
