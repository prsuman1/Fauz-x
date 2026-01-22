# FaujX JD-CV Matching System

AI-powered Job Description and CV matching system for entry-level hiring (0-3 years experience).

## Features

- **JD-CV Matching**: Upload a CV and match against job descriptions with AI-powered scoring
- **Question Generation**: Generate technical interview questions based on matched skills
- **Smart Scoring**: Accurate skill matching without hallucination
- **CSV Logging**: Track all match results for analytics

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file:

```env
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
DEFAULT_MODEL=anthropic/claude-3-haiku
FALLBACK_MODEL=qwen/qwen3-8b
APP_NAME=FaujX JD-CV Matcher
APP_ENV=production
DEBUG=false
API_TIMEOUT_SECONDS=30
```

### 3. Run the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 4. Access the Application

- Landing Page: http://localhost:8000/
- JD-CV Match: http://localhost:8000/jd-cv-match
- Question Generator: http://localhost:8000/question-gen

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/jd-cv-match` | POST | Match CV against JD |
| `/api/v1/generate-questions` | POST | Generate interview questions |

## Project Structure

```
JD-CV_Matching/
├── app/
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── routers/             # API routes
│   │   ├── matching.py      # JD-CV matching endpoint
│   │   └── questions.py     # Question generation endpoint
│   ├── services/            # Business logic
│   │   ├── openrouter_client.py
│   │   ├── jd_cv_matcher.py
│   │   ├── question_generator.py
│   │   └── csv_logger.py
│   ├── models/              # Pydantic schemas
│   ├── prompts/             # LLM prompts
│   ├── utils/               # Utilities
│   └── static/              # HTML templates
├── data/
│   └── logs/                # CSV logs
├── uploads/                 # Temporary file uploads
├── .env                     # Environment config
├── .gitignore
├── requirements.txt
└── README.md
```

## Scoring System

| Score | Grade | Recommendation |
|-------|-------|----------------|
| 85-100 | EXCELLENT | STRONG_HIRE |
| 80-84 | GOOD | SHORTLIST |
| 70-79 | MODERATE | MAYBE |
| 55-69 | WEAK | REJECT |
| 0-54 | POOR | REJECT |

## License

Proprietary - FaujX
