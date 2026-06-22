import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter
from gyaanv2.models import Chunk, LoadedDocument

class Chunker:
    def __init__(self, size:int, overlap:int):
        self.splitter=RecursiveCharacterTextSplitter(chunk_size=size, chunk_overlap=overlap, length_function=len)

    def chunk(self, document_id:int, doc:LoadedDocument):
        base={
            'document_id':document_id,
            'drive_file_id':doc.drive_file_id,
            'document_name':doc.name,
            'file_type':doc.file_type,
            'page_number':doc.page_number,
            'sheet_name':doc.sheet_name,
            'slide_number':doc.slide_number,
            'image_number':doc.image_number,
            'content_source':doc.content_source,
            'modified_time':doc.modified_time
        }

        for idx,text in enumerate(self.splitter.split_text(doc.content or '')):
            if not text.strip():
                continue

            cid=str(uuid.uuid5(uuid.NAMESPACE_URL, f'{document_id}:{idx}:{text[:80]}'))

            yield Chunk(cid, document_id, text, {**base, 'chunk_index':idx})