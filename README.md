# local-claim-intake

A small, **local, privacy-first** service that reads a free-text insurance claim and returns a
**typed** extraction plus a **human-in-the-loop gate** verdict — the model runs on-device, so
policyholder data never leaves the machine.

> **Honest framing.** Illustrative, not production. Synthetic data only. AI-assisted build;
> the design decisions are the author's own. Any speed/quality figures are illustrative, not benchmarks.

## Status

It.1 — FastAPI service scaffold. Health endpoint live; extraction endpoint next.

## Run

1. Install [Ollama](https://ollama.com) (macOS, Linux or Windows) and pull the model:
   `ollama pull qwen3.5:4b` (~3.4 GB)
2. Start the service:

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Defaults point at Ollama on `localhost:11434`. Any other OpenAI-compatible local server works too
(e.g. OMLX on Apple Silicon) — copy `.env.example` to `.env` and change the `ENGINE_*` values.
