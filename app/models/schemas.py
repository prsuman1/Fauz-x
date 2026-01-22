from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class MatchGrade(str, Enum):
    STRONG_HIRE = "STRONG_HIRE"
    SHORTLIST = "SHORTLIST"
    REJECT = "REJECT"


class ExperienceType(str, Enum):
    FRESHER = "fresher"
    INTERN = "intern"
    JUNIOR = "junior"


class DomainMatch(str, Enum):
    EXACT = "exact"
    CLOSE = "close"
    PARTIAL = "partial"
    MISMATCH = "mismatch"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# JD Models
class JDDetails(BaseModel):
    icon: Optional[str] = None
    title: str
    skills: List[str]
    niceToHave: Optional[List[str]] = []
    demandLevel: Optional[str] = None
    description: str
    responsibilities: List[str]


class JDInput(BaseModel):
    details: JDDetails
    capabilities: List[str]


# Match Analysis Models
class SkillAnalysis(BaseModel):
    matched_required: List[str] = Field(default_factory=list)
    missing_required: List[str] = Field(default_factory=list)
    matched_preferred: List[str] = Field(default_factory=list)
    missing_preferred: List[str] = Field(default_factory=list)
    additional_relevant: List[str] = Field(default_factory=list)
    skill_match_percentage: float = 0
    transferable_skills_note: Optional[str] = None
    skill_concerns: Optional[str] = None


class ExperienceAnalysis(BaseModel):
    total_years: float = 0
    relevant_years: float = 0
    relevance_score: float = 0
    experience_type: str = "fresher"
    key_experiences: List[str] = Field(default_factory=list)
    experience_quality: str = "medium"
    domain_match: str = "partial"
    notes: Optional[str] = None


class EducationAnalysis(BaseModel):
    requirement_met: bool = True
    degree: Optional[str] = None
    relevance: str = "medium"
    notes: Optional[str] = None


class RiskAssessment(BaseModel):
    risk_level: str = "medium"
    primary_risk: Optional[str] = None
    secondary_risks: List[str] = Field(default_factory=list)
    mitigation: Optional[str] = None
    hiring_risk_score: int = 5


class MatchResult(BaseModel):
    score: int = Field(ge=0, le=100)
    grade: MatchGrade
    summary: str
    skill_analysis: SkillAnalysis
    experience_analysis: ExperienceAnalysis
    education_analysis: Optional[EducationAnalysis] = None
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    red_flags: List[str] = Field(default_factory=list)
    risk_assessment: RiskAssessment
    recommendation: str
    recommendation_reason: str
    confidence_level: str = "medium"
    interview_focus_areas: List[str] = Field(default_factory=list)
    onboarding_suggestions: List[str] = Field(default_factory=list)
    final_verdict: str


# MCQ Models
class MCQQuestion(BaseModel):
    id: int
    skill_tested: str
    difficulty: str = "medium"  # easy, medium, hard
    question: str
    options: Dict[str, str]  # {"A": "...", "B": "...", "C": "...", "D": "..."}
    correct_answer: str  # "A", "B", "C", or "D"


class MCQTest(BaseModel):
    total_questions: int
    role_type: str
    questions: List[MCQQuestion]


# MCQ Models for Frontend (without correct answers)
class MCQQuestionForFrontend(BaseModel):
    id: int
    skill_tested: str
    difficulty: str = "medium"
    question: str
    options: Dict[str, str]


class MCQTestForFrontend(BaseModel):
    total_questions: int
    role_type: str
    questions: List[MCQQuestionForFrontend]


class MCQSubmission(BaseModel):
    answers: Dict[int, str]  # {question_id: selected_option}


class MCQResult(BaseModel):
    total_questions: int
    correct_answers: int
    wrong_answers: int
    score_percentage: float
    passed: bool
    details: List[Dict[str, Any]]  # Details of each question with correct/wrong


# API Request/Response Models
class AnalyzeRequest(BaseModel):
    jd_text: Optional[str] = None
    jd_file_path: Optional[str] = None


class AnalyzeResponse(BaseModel):
    success: bool
    message: Optional[str] = None
    match_result: Optional[MatchResult] = None
    mcq_test: Optional[MCQTestForFrontend] = None  # Only present if score >= 80
    mcq_error: Optional[str] = None  # Error message if MCQ generation failed
    session_id: Optional[str] = None  # For MCQ evaluation
    cv_filename: Optional[str] = None
    jd_title: Optional[str] = None
