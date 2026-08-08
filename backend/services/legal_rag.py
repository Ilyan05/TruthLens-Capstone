import os
from backend import config
_vs=None;_failed=False
def is_legal_claim(text):
    if not text:return False
    low=text.lower();return any(k in low for k in config.LEGAL_TRIGGERS)
def _emb():
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(model_name=config.LEGAL_EMBED_MODEL)
def _law_name(pdf):
    n=pdf.lower()
    if "bns" in n or "nyaya" in n:return "BNS 2023"
    if "ipc" in n or "penal" in n:return "IPC 1860 (repealed 2024, reference only)"
    if "const" in n:return "Constitution of India"
    return pdf
def build_index():
    from langchain_community.document_loaders import PyPDFLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_chroma import Chroma
    if not os.path.isdir(config.LEGAL_DIR):return f"Legal dir not found: {config.LEGAL_DIR}"
    pdfs=[f for f in os.listdir(config.LEGAL_DIR) if f.lower().endswith(".pdf")]
    if not pdfs:return f"No PDFs in {config.LEGAL_DIR}. Add bns_2023.pdf, ipc_1860.pdf, constitution.pdf"
    docs=[]
    for pdf in pdfs:
        try:
            loaded=PyPDFLoader(os.path.join(config.LEGAL_DIR,pdf)).load()
            law=_law_name(pdf)
            for d in loaded:d.metadata["law"]=law
            docs.extend(loaded);print(f"  loaded {pdf} -> {law} ({len(loaded)} pages)")
        except Exception as e:print("  skip",pdf,e)
    if not docs:return "No readable pages."
    chunks=RecursiveCharacterTextSplitter(chunk_size=config.LEGAL_CHUNK_SIZE,chunk_overlap=config.LEGAL_CHUNK_OVERLAP).split_documents(docs)
    Chroma.from_documents(chunks,_emb(),persist_directory=config.LEGAL_DB_DIR)
    return f"Indexed {len(chunks)} chunks from {len(pdfs)} PDF(s) -> {config.LEGAL_DB_DIR}"
def _load():
    global _vs,_failed
    if _vs is not None or _failed:return _vs
    if not os.path.isdir(config.LEGAL_DB_DIR):_failed=True;return None
    try:
        from langchain_chroma import Chroma
        _vs=Chroma(persist_directory=config.LEGAL_DB_DIR,embedding_function=_emb())
    except Exception:_failed=True;_vs=None
    return _vs
def search_law(query,top_k=None):
    if not config.LEGAL_RAG_ENABLED:return []
    store=_load()
    if store is None:return []
    try:hits=store.similarity_search(query,k=top_k or config.LEGAL_TOP_K)
    except Exception:return []
    out=[]
    for h in hits:
        law=h.metadata.get("law","Indian Law");page=h.metadata.get("page","")
        out.append({"title":f"{law}"+(f" (p.{page})" if page!="" else ""),"url":"","source_type":"legal","snippet":h.page_content[:400].strip(),"law":law})
    return out
if __name__=="__main__":
    import sys
    print(build_index() if len(sys.argv)>1 and sys.argv[1]=="build" else "Usage: python -m backend.services.legal_rag build")
