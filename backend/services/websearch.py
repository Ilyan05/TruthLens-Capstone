from urllib.parse import urlparse
from backend import config


# ---------- helpers ----------
def _domain(url: str) -> str:
    try:
        d = urlparse(url).netloc.lower()
        return d[4:] if d.startswith("www.") else d
    except Exception:
        return ""


def _classify_source(url: str) -> str:
    """Tag a URL as factcheck | news | official | encyclopedia | web."""
    d = _domain(url)
    if not d:
        return "web"
    if "wikipedia.org" in d:
        return "encyclopedia"
    if any(fc in d for fc in config.FACTCHECK_SITES):
        # pib.gov.in is government/official
        return "official" if "pib.gov.in" in d else "factcheck"
    if any(ns in d for ns in config.INDIA_NEWS_SITES):
        return "news"
    if d.endswith(".gov") or ".gov." in d:
        return "official"
    return "web"


def _import_ddgs():
    """Support both the new 'ddgs' package and the old 'duckduckgo_search'."""
    try:
        from ddgs import DDGS          # new package name
        return DDGS
    except Exception:
        pass
    try:
        from duckduckgo_search import DDGS   # old package name, in case there is an issue with the new onee
        return DDGS
    except Exception:
        return None


def _ddg_text(query: str, max_results: int):
    """Run one DuckDuckGo text search; return list of {title,url,snippet}."""
    DDGS = _import_ddgs()
    if DDGS is None:
        return []
    out = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                out.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", "") or r.get("link", "") or r.get("url", ""),
                    "snippet": r.get("body", "") or r.get("snippet", ""),
                })
    except Exception:
        return out
    return out


def _wikipedia(query: str):
    """Fetch a short Wikipedia summary as one evidence item (or None)."""
    try:
        import wikipedia
    except Exception:
        return None
    try:
        wikipedia.set_lang("en")
        hits = wikipedia.search(query, results=1)
        if not hits:
            return None
        summary = wikipedia.summary(hits[0], sentences=config.WIKI_SENTENCES,
                                    auto_suggest=False, redirect=True)
        page = wikipedia.page(hits[0], auto_suggest=False, redirect=True)
        return {
            "title": f"Wikipedia: {hits[0]}",
            "url": getattr(page, "url", ""),
            "snippet": summary,
        }
    except Exception:
        return None


def _site_filter_query(query: str, sites: list) -> str:
    """Build a DuckDuckGo query restricted to a set of domains."""
    ors = " OR ".join(f"site:{s}" for s in sites)
    return f"{query} ({ors})"


def _dedupe(items: list) -> list:
    seen, out = set(), []
    for it in items:
        url = it.get("url", "")
        key = url or it.get("title", "")
        if key and key not in seen:
            seen.add(key)
            out.append(it)
    return out


# ---------- main entry ----------
def search_evidence(search_query: str, claim_text: str = "") -> list:
    """
    Return a list of raw evidence dicts:
        {title, url, source_type, snippet}
    (stance is added later by the Context-NL Builder.)
    """
    query = (search_query or claim_text or "").strip()
    if not query:
        return []

    per = config.SEARCH_PER_SOURCE
    collected = []

    # 1) fact-check sites
    collected += _ddg_text(_site_filter_query(query, config.FACTCHECK_SITES), per)
    # 2) India news sites
    collected += _ddg_text(_site_filter_query(query, config.INDIA_NEWS_SITES), per)
    # 3) general web
    collected += _ddg_text(query, per)

    collected = _dedupe(collected)

    # tag source types
    evidence = []
    for it in collected:
        evidence.append({
            "title": it.get("title", "")[:200],
            "url": it.get("url", ""),
            "source_type": _classify_source(it.get("url", "")),
            "snippet": (it.get("snippet", "") or "")[:400],
        })

    # 4) Wikipedia (always try — great for people/history/facts)
    wiki = _wikipedia(query)
    if wiki:
        evidence.append({
            "title": wiki["title"],
            "url": wiki["url"],
            "source_type": "encyclopedia",
            "snippet": wiki["snippet"][:400],
        })

    # cap total
    return evidence[: config.SEARCH_MAX_RESULTS]
