"""Environment-driven settings. No API keys or model names are hardcoded."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_ROOT.parent

# .env lives at the project root (shared by backend and frontend tooling),
# not inside backend/ -- load it explicitly so this works regardless of
# which directory the app is launched from.
load_dotenv(PROJECT_ROOT / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
FALLBACK_MODEL_NAME = os.getenv("FALLBACK_MODEL_NAME", "gpt-3.5-turbo")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

VISION_LLM_ENABLED = os.getenv("VISION_LLM_ENABLED", "false").lower() == "true"

# Absolute by default so it resolves correctly no matter the launch cwd;
# still overridable via the INVENTORY_PATH env var.
INVENTORY_PATH = os.getenv("INVENTORY_PATH", str(BACKEND_ROOT / "data" / "inventory.csv"))

# Dev-only: frontend is a static page served from a different origin/port.
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ALLOWED_ORIGINS", "*")
