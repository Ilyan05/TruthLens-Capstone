import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_CLAIMS = [
    {"claim": "J.P. Morgan was Indian", "expected": "Fake"},
    {"claim": "The Sun rises in the east", "expected": "Real"},
    {"claim": "The Great Wall of China is visible from space with the naked eye", "expected": "Fake"},
    {"claim": "Water boils at 100 degrees Celsius at sea level", "expected": "Real"},
    {"claim": "Humans only use 10 percent of their brain", "expected": "Fake"},
]

def _run_pipeline(claim_text):
    """Run the TruthLens pipeline once and collect (answer, contexts)."""
    from backend.agents import claim_agent, pregrounder
    from backend.services import websearch, context_builder
    from backend.graph import verification_graph
    claim = claim_agent.extract_claim(claim_text)
    pg = pregrounder.pre_ground(claim["claim_text"])
    raw = websearch.search_evidence(claim.get("search_query", ""), claim["claim_text"])
    ctx = context_builder.build_context(claim["claim_text"], raw)
    final = None
    for name, payload in verification_graph.tot_steps(
            claim["claim_text"], claim.get("search_query", ""), ctx["evidence"], pg):
        if name == "verdict":
            final = payload
    contexts = [e.get("snippet", "") for e in ctx["evidence"][:5]] or ["(no evidence)"]
    answer = final["summary"] if final else "Inconclusive"
    return answer, contexts, (final["verdict"] if final else "Inconclusive")

def run_ragas():
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy
    from datasets import Dataset
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
    from backend import config

    rows = {"question": [], "answer": [], "contexts": [], "ground_truth": []}
    print(f"Running pipeline on {len(TEST_CLAIMS)} test claims...")
    for i, t in enumerate(TEST_CLAIMS, 1):
        try:
            ans, ctxs, verdict = _run_pipeline(t["claim"])
            rows["question"].append(t["claim"])
            rows["answer"].append(ans)
            rows["contexts"].append(ctxs)
            rows["ground_truth"].append(t["expected"])
            print(f"  [{i}] {t['claim'][:40]}... -> {verdict}")
        except Exception as e:
            print(f"  [{i}] error: {e}")

    ds = Dataset.from_dict(rows)
    judge = ChatGoogleGenerativeAI(model=config.MODEL_REASONING,
                                   google_api_key=config.GEMINI_API_KEY, temperature=0)
    emb = GoogleGenerativeAIEmbeddings(model="models/embedding-001",
                                       google_api_key=config.GEMINI_API_KEY)
    print("\nScoring with RAGAS (Gemini as judge)...")
    result = evaluate(ds, metrics=[faithfulness, answer_relevancy], llm=judge, embeddings=emb)
    print("\n=== RAGAS SCORES ===")
    print(result)
    os.makedirs("evaluation", exist_ok=True)
    with open("evaluation/ragas_report.json", "w") as f:
        json.dump({k: float(v) for k, v in result.items()}, f, indent=2)
    print("\nSaved -> evaluation/ragas_report.json")


if __name__ == "__main__":
    from backend import config
    if not config.llm_ready():
        print("[!] No Gemini API key. Add GEMINI_API_KEY_1..6 to .env first.")
    else:
        run_ragas()
