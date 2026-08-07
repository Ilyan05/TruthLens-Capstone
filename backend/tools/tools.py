from langchain_core.tools import tool
from backend.services import websearch, legal_rag


@tool
def web_search_tool(query: str) -> list:
    """Search the web for evidence about a claim. Returns a list of sources with
    title, url, source_type (factcheck/news/official/encyclopedia/web) and snippet.
    Use this for any factual claim that needs external verification."""
    return websearch.search_evidence(query, query)


@tool
def legal_rag_tool(query: str) -> list:
    """Look up relevant Indian law — Bharatiya Nyaya Sanhita (BNS) 2023 and the
    Constitution of India — for legal/constitutional claims (e.g. 'anti-national',
    sedition, unconstitutional, fundamental rights). Returns matching law sections.
    Use ONLY when the claim involves law, legality, rights, or constitutionality."""
    return legal_rag.search_law(query)


# registry (used by the graph)
ALL_TOOLS = [web_search_tool, legal_rag_tool]
TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}
