import sys
import httpx

from app.config import settings
from app.db import check_db_health, get_db_context
from app.models.entities import TranscriptSource, TranscriptChunk


def run_checks():
    print("=== The Lenny Growth Assistant: Pre-flight Verification ===")
    
    # 1. Check Database
    print(f"[1/4] Checking Database ({settings.database_url})...")
    if check_db_health():
        print("  [OK] Database connection established successfully.")
    else:
        print("  [FAIL] Database connection FAILED.")
        sys.exit(1)

    # 2. Check Seed Transcripts & Embeddings
    print("[2/4] Verifying Ingested Knowledge Base...")
    with get_db_context() as db:
        source_count = db.query(TranscriptSource).count()
        chunk_count = db.query(TranscriptChunk).count()
        valid_chunks = (
            db.query(TranscriptChunk)
            .filter(TranscriptChunk.embedding_local.isnot(None))
            .all()
        )
        valid_3072_count = sum(1 for c in valid_chunks if len(c.embedding_local) == 3072)
        print(f"  [OK] Sources in DB: {source_count}, Chunks in DB: {chunk_count} (3072-dim: {valid_3072_count})")
        if source_count == 0 or chunk_count == 0 or valid_3072_count == 0:
            print("  ! Warning: Knowledge base incomplete or un-embedded. Run 'python -m scripts.ingest'")

    # 3. Check Local Ollama & phi3 Model
    print(f"[3/4] Checking Local Ollama Service ({settings.ollama_base_url})...")
    try:
        resp = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=3.0)
        if resp.status_code == 200:
            models = [m.get("name") for m in resp.json().get("models", [])]
            print(f"  [OK] Ollama reachable. Available models: {models}")
            has_phi3 = any("phi3" in m.lower() for m in models)
            if has_phi3:
                print("  [OK] Phi3 model detected in Ollama.")
                # Quick test of embeddings endpoint
                emb_resp = httpx.post(
                    f"{settings.ollama_base_url}/api/embeddings",
                    json={"model": settings.ollama_embed_model, "prompt": "health check"},
                    timeout=5.0
                )
                if emb_resp.status_code == 200:
                    emb = emb_resp.json().get("embedding", [])
                    print(f"  [OK] Phi3 embeddings operational (vector length: {len(emb)}).")
                else:
                    print(f"  ! Ollama embedding test returned status {emb_resp.status_code}")
            else:
                print(f"  ! Warning: Configured model '{settings.ollama_model}' not found in Ollama list.")
        else:
            print(f"  ! Ollama returned status {resp.status_code}")
    except Exception as e:
        print(f"  ! Ollama unreachable at {settings.ollama_base_url} ({e}).")
        print("    (Expected if Ollama is not started yet; fallback is active.)")

    # 4. Check Cloud Provider Configuration
    print(f"[4/4] Checking Cloud Provider ({settings.llm_provider})...")
    if settings.llm_provider == "anthropic":
        if settings.anthropic_api_key:
            print("  [OK] Anthropic API key configured.")
        else:
            print("  ! Anthropic API key is NOT set. Will fallback to Ollama if fallback enabled.")
    else:
        print(f"  [OK] Provider configured for local demo ({settings.llm_provider} / {settings.llm_model}).")
    
    print("\n[OK] Pre-flight checks completed.")


if __name__ == "__main__":
    run_checks()
