"""Export OpenAPI spec from the FastAPI app to docs/openapi.json."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env.development")

from app.main import app

spec = app.openapi()
out = Path(__file__).resolve().parent.parent / "docs" / "openapi.json"
out.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Exported to {out}")
