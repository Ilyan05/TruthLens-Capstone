from langchain_core.tools import tool
from backend.services import websearch, legal_rag
@tool
def web_search_tool(query:str)->list:
    """Search the web for evidence about a claim (news, fact-check, wiki)."""
    return websearch.search_evidence(query,query)
@tool
def legal_rag_tool(query:str)->list:
    """Look up Indian law (BNS 2023, IPC 1860, Constitution) for legal/constitutional claims."""
    return legal_rag.search_law(query)
ALL_TOOLS=[web_search_tool,legal_rag_tool]
TOOLS_BY_NAME={t.name:t for t in ALL_TOOLS}
