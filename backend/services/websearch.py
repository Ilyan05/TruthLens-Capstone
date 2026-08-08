from urllib.parse import urlparse
from backend import config
def _domain(u):
    try:
        d=urlparse(u).netloc.lower();return d[4:] if d.startswith("www.") else d
    except Exception:return ""
def _classify(u):
    d=_domain(u)
    if not d:return "web"
    if "wikipedia.org" in d:return "encyclopedia"
    if any(f in d for f in config.FACTCHECK_SITES):return "official" if "pib.gov.in" in d else "factcheck"
    if any(n in d for n in config.INDIA_NEWS_SITES):return "news"
    if d.endswith(".gov") or ".gov." in d:return "official"
    return "web"
def _ddgs():
    try:
        from ddgs import DDGS;return DDGS
    except Exception:pass
    try:
        from duckduckgo_search import DDGS;return DDGS
    except Exception:return None
def _ddg(q,n):
    D=_ddgs()
    if D is None:return []
    out=[]
    try:
        with D() as d:
            for r in d.text(q,max_results=n):
                out.append({"title":r.get("title",""),"url":r.get("href","") or r.get("link","") or r.get("url",""),"snippet":r.get("body","") or r.get("snippet","")})
    except Exception:return out
    return out
def _wiki(q):
    try:import wikipedia
    except Exception:return None
    try:
        wikipedia.set_lang("en");h=wikipedia.search(q,results=1)
        if not h:return None
        s=wikipedia.summary(h[0],sentences=config.WIKI_SENTENCES,auto_suggest=False,redirect=True)
        pg=wikipedia.page(h[0],auto_suggest=False,redirect=True)
        return {"title":f"Wikipedia: {h[0]}","url":getattr(pg,"url",""),"snippet":s}
    except Exception:return None
def _sq(q,sites):return f"{q} ({' OR '.join('site:'+s for s in sites)})"
def _dedupe(items):
    seen,out=set(),[]
    for it in items:
        k=it.get("url","") or it.get("title","")
        if k and k not in seen:seen.add(k);out.append(it)
    return out
def search_evidence(search_query,claim_text=""):
    q=(search_query or claim_text or "").strip()
    if not q:return []
    per=config.SEARCH_PER_SOURCE;c=[]
    c+=_ddg(_sq(q,config.FACTCHECK_SITES),per);c+=_ddg(_sq(q,config.INDIA_NEWS_SITES),per);c+=_ddg(q,per)
    c=_dedupe(c)
    ev=[{"title":it.get("title","")[:200],"url":it.get("url",""),"source_type":_classify(it.get("url","")),"snippet":(it.get("snippet","") or "")[:400]} for it in c]
    w=_wiki(q)
    if w:ev.append({"title":w["title"],"url":w["url"],"source_type":"encyclopedia","snippet":w["snippet"][:400]})
    return ev[:config.SEARCH_MAX_RESULTS]
