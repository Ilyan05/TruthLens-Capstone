"""TruthLens - single entry point.  Run: python run.py  -> http://localhost:8000"""
import uvicorn

if __name__ == "__main__":
    print("=" * 55)
    print("  TruthLens starting...")
    print("  Open in browser:  http://localhost:8000")
    print("  Press CTRL+C to stop")
    print("=" * 55)
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
