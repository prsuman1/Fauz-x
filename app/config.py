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

# CSV Log file
MATCH_LOG_FILE = LOGS_DIR / "match_results.csv"
