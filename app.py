import streamlit as st
from gyaanv2.rag.service import RAGService

st.set_page_config(page_title='Orion - Context Layer', layout='wide')
st.title('Orion - Context Layer')

# @st.cache_resource(show_spinner='Loading models and stores...')
# def service(): return RAGService()
# Keep RAGService uncached because it owns SQLite/Qdrant clients,
# which are not safe to reuse across Streamlit script threads.
with st.spinner('Loading models and stores...'):
    svc=RAGService()

page=st.sidebar.radio('Page', ['Settings','Documents','Chat'])

if page=='Settings':
    st.header('Settings')
    url=st.text_input('Google Drive folder or document link')
    if st.button('Add source', type='primary') and url:
        try: st.success(f'Added source #{svc.add_source(url)}')
        except Exception as e: st.error(e)
    c1,c2=st.columns(2)
    if c1.button('Sync all active sources'):
        with st.spinner('Syncing...'):
            try: st.success(f'Synced {svc.sync_all()} document parts')
            except Exception as e: st.error(e)
    st.subheader('Connected sources')
    for s in svc.db.list_sources():
        with st.expander(f"{s['name']} — {s['status']}"):
            st.write(dict(s))
            a,b=st.columns(2)
            if a.button('Sync/Re-sync', key=f"sync{s['id']}"):
                with st.spinner('Syncing source...'):
                    try: st.success(f"Synced {svc.sync_source(s['id'])} document parts")
                    except Exception as e: st.error(e)
            if b.button('Remove source', key=f"rm{s['id']}"):
                ids=svc.db.remove_source(s['id'])
                for did in ids: svc.vectors.delete_document(did)
                st.warning('Removed source and indexed chunks. Refresh to update list.')
elif page=='Documents':
    st.header('Documents')
    rows=[dict(r) for r in svc.db.list_documents()]
    if rows: st.dataframe(rows, use_container_width=True)
    else: st.info('No indexed documents yet.')
else:
    st.header('Chat')
    q=st.text_input('Ask a question')
    if st.button('Ask', type='primary') and q:
        with st.spinner('Retrieving and answering...'):
            ans,ctx=svc.ask(q)
        st.subheader('Answer'); st.write(ans)
        st.subheader('Retrieved sources')
        for c in ctx:
            with st.expander(f"{c['citation']} — score {c['score']:.3f}"):
                st.write(c['content'])
                st.json(c['payload'])
