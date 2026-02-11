import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
UPLOADS_DIR = BASE_DIR / "uploads"
CV_DIR = BASE_DIR / "CV"
JD_DIR = BASE_DIR / "JD"

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# OpenRouter API
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

# Multi-key support: collect OPENROUTER_API_KEY, OPENROUTER_API_KEY_1, ..., OPENROUTER_API_KEY_20
OPENROUTER_API_KEYS: list[str] = []
_base_key = os.getenv("OPENROUTER_API_KEY", "").strip()
if _base_key:
    OPENROUTER_API_KEYS.append(_base_key)
for i in range(1, 21):
    _k = os.getenv(f"OPENROUTER_API_KEY_{i}", "").strip()
    if _k and _k not in OPENROUTER_API_KEYS:
        OPENROUTER_API_KEYS.append(_k)

API_KEY_COOLDOWN_SECONDS = int(os.getenv("API_KEY_COOLDOWN_SECONDS", "60"))

# Model Configuration
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "anthropic/claude-3-haiku")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "qwen/qwen3-8b")
CODE_MODEL = os.getenv("CODE_MODEL", "anthropic/claude-sonnet-4")

# App Settings
APP_NAME = os.getenv("APP_NAME", "FaujX JD-CV Matcher")
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# Timeouts
API_TIMEOUT_SECONDS = int(os.getenv("API_TIMEOUT_SECONDS", "60"))

# Scoring Thresholds
REJECT_THRESHOLD = 87  # Score < 87 = REJECT
SHORTLIST_THRESHOLD = 95  # Score 87-94 = SHORTLIST, 95+ = MUST_HIRE (STRONG_HIRE)

# MCQ Settings
MIN_MCQ_QUESTIONS = 15
MCQ_PASS_PERCENTAGE = 60

# Code Check Settings
CODE_CHECK_PASS_THRESHOLD = 80  # Score >= 80 is considered passed
CODE_CHECK_MAX_SCORE = 100

# Database
DB_HOST = os.getenv("DATABASE_HOST", "localhost")
DB_PORT = int(os.getenv("DATABASE_PORT", "5432"))
DB_NAME = os.getenv("DATABASE_NAME", "faujx_dev")
DB_USER = os.getenv("DATABASE_USER", "suman")
DB_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
MCQ_DATABASE_NAME = os.getenv("MCQ_DATABASE_NAME", "mcq_database")
MCQ_DB_HOST = os.getenv("MCQ_DATABASE_HOST", "localhost")
MCQ_DB_PORT = int(os.getenv("MCQ_DATABASE_PORT", "5432"))
MCQ_DB_USER = os.getenv("MCQ_DATABASE_USER", "suman")
MCQ_DB_PASSWORD = os.getenv("MCQ_DATABASE_PASSWORD", "")

# CSV Log file
MATCH_LOG_FILE = LOGS_DIR / "match_results.csv"
