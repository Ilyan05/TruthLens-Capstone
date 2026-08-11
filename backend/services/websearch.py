from urllib.parse import urlparse

from backend import config


# --------------------------------------------------
# Extract domain from URL
# --------------------------------------------------
def _domain(url):
    try:
        domain = urlparse(url).netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


# --------------------------------------------------
# Classify source type
# --------------------------------------------------
def _classify(url):
    domain = _domain(url)

    if not domain:
        return "web"

    if "wikipedia.org" in domain:
        return "encyclopedia"

    if any(site in domain for site in config.FACTCHECK_SITES):
        if "pib.gov.in" in domain:
            return "official"
        return "factcheck"

    if any(site in domain for site in config.INDIA_NEWS_SITES):
        return "news"

    if domain.endswith(".gov") or ".gov." in domain:
        return "official"

    return "web"


# --------------------------------------------------
# Load DuckDuckGo search library
# Supports both packages:
#   ddgs
#   duckduckgo_search
# --------------------------------------------------
def _ddgs():
    try:
        from ddgs import DDGS
        return DDGS

    except Exception:
        pass

    try:
        from duckduckgo_search import DDGS
        return DDGS

    except Exception:
        return None


# --------------------------------------------------
# Perform DuckDuckGo search
# --------------------------------------------------
def _ddg(query, limit):
    DDGS = _ddgs()

    if DDGS is None:
        return []

    results = []

    try:
        with DDGS() as searcher:
            for item in searcher.text(query, max_results=limit):

                results.append(
                    {
                        "title": item.get("title", ""),
                        "url": (
                            item.get("href", "")
                            or item.get("link", "")
                            or item.get("url", "")
                        ),
                        "snippet": (
                            item.get("body", "")
                            or item.get("snippet", "")
                        ),
                    }
                )

    except Exception:
        return results

    return results


# --------------------------------------------------
# Fetch Wikipedia summary
# --------------------------------------------------
def _wiki(query):
    try:
        import wikipedia

    except Exception:
        return None

    try:
        wikipedia.set_lang("en")

        hits = wikipedia.search(
            query,
            results=1
        )

        if not hits:
            return None

        summary = wikipedia.summary(
            hits[0],
            sentences=config.WIKI_SENTENCES,
            auto_suggest=False,
            redirect=True,
        )

        page = wikipedia.page(
            hits[0],
            auto_suggest=False,
            redirect=True,
        )

        return {
            "title": f"Wikipedia: {hits[0]}",
            "url": getattr(page, "url", ""),
            "snippet": summary,
        }

    except Exception:
        return None


# --------------------------------------------------
# Create site-filtered search query
# Example:
# AI (site:pib.gov.in OR site:factcheck.org)
# --------------------------------------------------
def _sq(query, sites):
    site_filter = " OR ".join(
        f"site:{site}"
        for site in sites
    )

    return f"{query} ({site_filter})"


# --------------------------------------------------
# Remove duplicate results
# --------------------------------------------------
def _dedupe(items):
    seen = set()
    output = []

    for item in items:
        key = (
            item.get("url", "")
            or item.get("title", "")
        )

        if key and key not in seen:
            seen.add(key)
            output.append(item)

    return output


# --------------------------------------------------
# Main Evidence Search Function
# --------------------------------------------------
def search_evidence(search_query, claim_text=""):

    query = (
        search_query
        or claim_text
        or ""
    ).strip()

    if not query:
        return []

    per_source = config.SEARCH_PER_SOURCE

    candidates = []

    # Search fact-check websites
    candidates += _ddg(
        _sq(query, config.FACTCHECK_SITES),
        per_source,
    )

    # Search trusted Indian news sites
    candidates += _ddg(
        _sq(query, config.INDIA_NEWS_SITES),
        per_source,
    )

    # General web search
    candidates += _ddg(
        query,
        per_source,
    )

    # Remove duplicate entries
    candidates = _dedupe(candidates)

    evidence = []

    # Format results
    for item in candidates:
        evidence.append(
            {
                "title": item.get("title", "")[:200],
                "url": item.get("url", ""),
                "source_type": _classify(
                    item.get("url", "")
                ),
                "snippet": (
                    item.get("snippet", "")
                    or ""
                )[:400],
            }
        )

    # Add Wikipedia result
    wiki_result = _wiki(query)

    if wiki_result:
        evidence.append(
            {
                "title": wiki_result["title"],
                "url": wiki_result["url"],
                "source_type": "encyclopedia",
                "snippet": wiki_result["snippet"][:400],
            }
        )

    # Limit final output
    return evidence[:config.SEARCH_MAX_RESULTS]