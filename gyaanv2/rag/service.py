import logging
from dataclasses import dataclass
from time import perf_counter

from gyaanv2.config import get_settings
from gyaanv2.ingestion.drive import GoogleDriveClient, parse_drive_link
from gyaanv2.llm.providers import LLM, NO_DATA
from gyaanv2.rag.chunking import Chunker
from gyaanv2.rag.embeddings import Embedder
from gyaanv2.rag.reranker import Reranker
from gyaanv2.storage.metadata import MetadataStore
from gyaanv2.storage.vector import VectorStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def citation(payload):
    bits=[payload.get('document_name','Unknown')]
    if payload.get('page_number'): bits.append(f"page {payload['page_number']}")
    if payload.get('sheet_name'): bits.append(f"sheet {payload['sheet_name']}")
    if payload.get('slide_number'): bits.append(f"slide {payload['slide_number']}")
    if payload.get('image_number'): bits.append(f"image {payload['image_number']}")
    bits.append(f"chunk {payload.get('chunk_index',0)}")
    return ' / '.join(map(str,bits))

@dataclass
class SyncStats:
    scanned_files: int = 0
    scanned_parts: int = 0
    indexed: int = 0
    skipped: int = 0

    def __iadd__(self, other):
        self.scanned_files += other.scanned_files
        self.scanned_parts += other.scanned_parts
        self.indexed += other.indexed
        self.skipped += other.skipped
        return self

    def __str__(self):
        return f'{self.indexed} re-indexed document parts, {self.skipped} unchanged document parts, {self.scanned_files} scanned files'


def document_coalesce_key(doc):
    key_parts = [doc.sheet_name or doc.page_number or doc.slide_number or 'main']
    if doc.content_source != 'text':
        key_parts.append(doc.content_source)
    if doc.image_number is not None:
        key_parts.append(f'image-{doc.image_number}')
    return ':'.join(map(str, key_parts))

class RAGService:
    def __init__(self):
        self.settings=get_settings(); self.db=MetadataStore(self.settings.sqlite_path); self.embedder=Embedder(self.settings.embedding_model)
        self.vectors=VectorStore(self.settings.qdrant_path, self.settings.qdrant_collection, self.embedder.dimension)
        self.chunker=Chunker(self.settings.chunk_size, self.settings.chunk_overlap); self.llm=LLM(self.settings)
        self.reranker = None
    def add_source(self,url):
        did,kind=parse_drive_link(url); drive=GoogleDriveClient(self.settings.google_credentials_file,self.settings.google_token_file); meta=drive.metadata(did)
        return self.db.add_source(url,did, 'folder' if meta['mimeType'].endswith('.folder') else kind, meta['name'])
    def sync_source(self, source_id:int):
        source=self.db.get_source(source_id); self.db.set_source_status(source_id,'syncing')
        try:
            drive=GoogleDriveClient(self.settings.google_credentials_file,self.settings.google_token_file); stats=SyncStats()
            for file in drive.iter_files(source['drive_id']):
                stats.scanned_files+=1
                for doc in drive.load_file(source_id,file):
                    stats.scanned_parts+=1
                    coalesce_key=document_coalesce_key(doc)
                    existing=self.db.get_document_by_drive_key(doc.source_id, doc.drive_file_id, doc.file_type, coalesce_key)
                    if existing and existing['modified_time'] == doc.modified_time:
                        stats.skipped+=1
                        continue
                    doc_id=self.db.replace_document(doc, coalesce_key)
                    chunks=list(self.chunker.chunk(doc_id, doc)); vecs=self.embedder.embed_texts([c.content for c in chunks]) if chunks else []
                    self.vectors.delete_document(doc_id); self.vectors.upsert_chunks(chunks, vecs); self.db.add_chunks(doc_id,chunks); stats.indexed+=1
            self.db.set_source_status(source_id,'synced'); return stats
        except Exception as e:
            self.db.set_source_status(source_id,'error',str(e)); raise
    def sync_all(self):
        total=SyncStats()
        for s in self.db.list_sources():
            if s['active']: total+=self.sync_source(s['id'])
        return total
    def _get_reranker(self):
        if self.reranker is None:
            self.reranker = Reranker(self.settings.RERANKER_MODEL)
        return self.reranker

    def _rerank_contexts(self, question:str, ctx:list[dict]):
        if not self.settings.ENABLE_RERANKER:
            selected = ctx[:self.settings.FINAL_CONTEXT_K]
            logger.info('Reranked chunk count: %s (reranker disabled)', len(selected))
            return selected

        try:
            started = perf_counter()
            reranked = self._get_reranker().rerank(question, ctx, self.settings.FINAL_CONTEXT_K)
            logger.info('Reranked chunk count: %s in %.3fs', len(reranked), perf_counter() - started)
            return reranked
        except Exception:
            logger.exception('Reranker failed; falling back to cosine similarity retrieval')
            return ctx[:self.settings.FINAL_CONTEXT_K]

    def ask(self, question:str):
        request_started = perf_counter()
        retrieval_started = perf_counter()
        qv=self.embedder.embed_query(question); hits=self.vectors.search(qv,self.settings.INITIAL_RETRIEVAL_K)
        ctx=[]
        for h in hits:
            score=float(h.score or 0)
            if score < self.settings.min_relevance_score: continue
            p=h.payload or {}; ctx.append({'score':score,'content':p.get('content',''),'citation':citation(p),'payload':p})
        logger.info('Retrieved chunk count: %s in %.3fs', len(ctx), perf_counter() - retrieval_started)
        if not ctx: return NO_DATA, []

        selected_ctx = self._rerank_contexts(question, ctx)
        logger.info('End-to-end retrieval context preparation latency: %.3fs', perf_counter() - request_started)
        answer=self.llm.answer(question, selected_ctx)
        if not answer.strip() or answer.strip()==NO_DATA: return NO_DATA, selected_ctx
        return answer, selected_ctx
