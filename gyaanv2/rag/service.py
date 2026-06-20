from gyaanv2.config import get_settings
from gyaanv2.ingestion.drive import GoogleDriveClient, parse_drive_link
from gyaanv2.llm.providers import LLM, NO_DATA
from gyaanv2.rag.chunking import Chunker
from gyaanv2.rag.embeddings import Embedder
from gyaanv2.storage.metadata import MetadataStore
from gyaanv2.storage.vector import VectorStore


def citation(payload):
    bits=[payload.get('document_name','Unknown')]
    if payload.get('page_number'): bits.append(f"page {payload['page_number']}")
    if payload.get('sheet_name'): bits.append(f"sheet {payload['sheet_name']}")
    if payload.get('slide_number'): bits.append(f"slide {payload['slide_number']}")
    bits.append(f"chunk {payload.get('chunk_index',0)}")
    return ' / '.join(map(str,bits))

class RAGService:
    def __init__(self):
        self.settings=get_settings(); self.db=MetadataStore(self.settings.sqlite_path); self.embedder=Embedder(self.settings.embedding_model)
        self.vectors=VectorStore(self.settings.qdrant_path, self.settings.qdrant_collection, self.embedder.dimension)
        self.chunker=Chunker(self.settings.chunk_size, self.settings.chunk_overlap); self.llm=LLM(self.settings)
    def add_source(self,url):
        did,kind=parse_drive_link(url); drive=GoogleDriveClient(self.settings.google_credentials_file,self.settings.google_token_file); meta=drive.metadata(did)
        return self.db.add_source(url,did, 'folder' if meta['mimeType'].endswith('.folder') else kind, meta['name'])
    def sync_source(self, source_id:int):
        source=self.db.get_source(source_id); self.db.set_source_status(source_id,'syncing')
        try:
            drive=GoogleDriveClient(self.settings.google_credentials_file,self.settings.google_token_file); count=0
            for file in drive.iter_files(source['drive_id']):
                for doc in drive.load_file(source_id,file):
                    key=doc.sheet_name or doc.page_number or doc.slide_number or 'main'
                    doc_id=self.db.replace_document(doc, str(key))
                    chunks=list(self.chunker.chunk(doc_id, doc)); vecs=self.embedder.embed_texts([c.content for c in chunks]) if chunks else []
                    self.vectors.delete_document(doc_id); self.vectors.upsert_chunks(chunks, vecs); self.db.add_chunks(doc_id,chunks); count+=1
            self.db.set_source_status(source_id,'synced'); return count
        except Exception as e:
            self.db.set_source_status(source_id,'error',str(e)); raise
    def sync_all(self):
        total=0
        for s in self.db.list_sources():
            if s['active']: total+=self.sync_source(s['id'])
        return total
    def ask(self, question:str):
        qv=self.embedder.embed_query(question); hits=self.vectors.search(qv,self.settings.retrieval_limit)
        ctx=[]
        for h in hits:
            score=float(h.score or 0)
            if score < self.settings.min_relevance_score: continue
            p=h.payload or {}; ctx.append({'score':score,'content':p.get('content',''),'citation':citation(p),'payload':p})
        if not ctx: return NO_DATA, []
        answer=self.llm.answer(question, ctx)
        if not answer.strip() or answer.strip()==NO_DATA: return NO_DATA, ctx
        return answer, ctx
