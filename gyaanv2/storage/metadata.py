import sqlite3
from pathlib import Path
from typing import Iterable, Optional
from gyaanv2.models import Source, utc_now


class MetadataStore:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self.connect() as c:
            c.executescript('''
            create table if not exists sources(
              id integer primary key autoincrement, url text not null unique, drive_id text not null,
              drive_kind text not null, name text not null, active integer not null default 1,
              status text not null default 'pending', last_sync_at text, error text, created_at text not null
            );
            create table if not exists documents(
              id integer primary key autoincrement, source_id integer not null, drive_file_id text not null,
              name text not null, mime_type text not null, file_type text not null, modified_time text,
              page_count integer, chunk_count integer not null default 0, last_sync_at text not null,
              coalesce_key text not null default 'main',
              unique(source_id, drive_file_id, file_type, coalesce_key)
            );
            create table if not exists document_keys(document_id integer primary key, coalesce_key text not null);
            create table if not exists chunks(
              id text primary key, document_id integer not null, chunk_index integer not null, content text not null,
              page_number integer, sheet_name text, slide_number integer, score real, created_at text not null
            );
            ''')
            cols = [r['name'] for r in c.execute('pragma table_info(documents)')]
            if 'coalesce_key' not in cols:
                c.execute('alter table documents add column coalesce_key text not null default \'main\'')

    def add_source(self, url, drive_id, drive_kind, name):
        with self.connect() as c:
            c.execute('insert into sources(url,drive_id,drive_kind,name,created_at) values(?,?,?,?,?) on conflict(url) do update set active=1,error=null,status=\'pending\'', (url, drive_id, drive_kind, name, utc_now()))
            return c.execute('select * from sources where url=?', (url,)).fetchone()['id']

    def list_sources(self) -> list[sqlite3.Row]:
        with self.connect() as c:
            return c.execute('select * from sources order by id desc').fetchall()

    def get_source(self, source_id:int):
        with self.connect() as c:
            return c.execute('select * from sources where id=?', (source_id,)).fetchone()

    def set_source_status(self, source_id:int, status:str, error: Optional[str]=None):
        with self.connect() as c:
            c.execute('update sources set status=?, error=?, last_sync_at=case when ?=\'synced\' then ? else last_sync_at end where id=?', (status, error, status, utc_now(), source_id))

    def remove_source(self, source_id:int):
        with self.connect() as c:
            doc_ids=[r['id'] for r in c.execute('select id from documents where source_id=?',(source_id,))]
            c.execute('delete from chunks where document_id in (%s)' % ','.join('?'*len(doc_ids)), doc_ids) if doc_ids else None
            c.execute('delete from documents where source_id=?',(source_id,))
            c.execute('update sources set active=0,status=\'removed\' where id=?',(source_id,))
        return doc_ids

    def get_document_by_drive_key(self, source_id:int, drive_file_id:str, file_type:str, coalesce_key:str):
        with self.connect() as c:
            return c.execute(
                'select * from documents where source_id=? and drive_file_id=? and file_type=? and coalesce_key=?',
                (source_id, drive_file_id, file_type, coalesce_key),
            ).fetchone()

    def replace_document(self, doc, coalesce_key='main') -> int:
        now=utc_now()
        with self.connect() as c:
            row=c.execute('select id from documents where source_id=? and drive_file_id=? and file_type=? and coalesce_key=?',(doc.source_id,doc.drive_file_id,doc.file_type,coalesce_key)).fetchone()
            if row:
                doc_id=row['id']; c.execute('delete from chunks where document_id=?',(doc_id,))
                c.execute('update documents set name=?,mime_type=?,modified_time=?,last_sync_at=?,chunk_count=0 where id=?',(doc.name,doc.mime_type,doc.modified_time,now,doc_id))
            else:
                cur=c.execute('insert into documents(source_id,drive_file_id,name,mime_type,file_type,modified_time,last_sync_at,coalesce_key) values(?,?,?,?,?,?,?,?)',(doc.source_id,doc.drive_file_id,doc.name,doc.mime_type,doc.file_type,doc.modified_time,now,coalesce_key))
                doc_id=cur.lastrowid
            return doc_id

    def add_chunks(self, document_id:int, chunks:Iterable):
        rows=[]
        for i,ch in enumerate(chunks):
            m=ch.metadata
            rows.append((ch.chunk_id,document_id,i,ch.content,m.get('page_number'),m.get('sheet_name'),m.get('slide_number'),utc_now()))
        with self.connect() as c:
            c.executemany('insert or replace into chunks(id,document_id,chunk_index,content,page_number,sheet_name,slide_number,created_at) values(?,?,?,?,?,?,?,?)', rows)
            c.execute('update documents set chunk_count=? where id=?',(len(rows),document_id))

    def list_documents(self):
        with self.connect() as c:
            return c.execute('select d.*, s.name as source_name from documents d join sources s on s.id=d.source_id order by d.last_sync_at desc').fetchall()
