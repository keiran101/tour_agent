# Tour Agent — AI 旅游行程规划助手

## Quick Commands
```bash
uv sync                          # Install dependencies
uv run uvicorn app.main:app --reload --port 8000  # Dev server
uv run ruff check .              # Lint
uv run pyright                   # Type check
docker compose up -d             # Full stack (DB + API + monitoring)
```

## Architecture
```
app/
  api/v1/          # FastAPI route handlers (auth, chat, trip)
  core/
    agent/         # Self-built ReAct agent loop (NO LangGraph)
    tools/         # Tour-specific tools (POI, weather, search, map)
    prompts/       # System prompt templates (.md files)
    config.py      # Settings from env vars
    logging.py     # structlog structured logging
    metrics.py     # Prometheus metrics
  models/          # SQLModel ORM (User, Session, Trip)
  schemas/         # Pydantic request/response schemas
  services/        # Business logic (LLM, memory, trip planning)
  utils/           # Shared utilities
```

## Key Design Decisions
- **No LangGraph / LangChain** — self-built agent loop for interview credibility
- **OpenAI-compatible protocol** — all LLMs (MiMo/DeepSeek/Qwen) accessed via `openai` SDK
- **pgvector self-implemented memory** — no mem0, every component explainable
- **structlog** for all logging, lowercase_underscore event names
- **tenacity** for all retry logic

## Code Rules
- All imports at top of file
- Use `async def` for I/O operations
- Type hints on all function signatures
- Log events as `logger.info("event_name", key=value)` — no f-strings
- Rate limiting on all API endpoints
