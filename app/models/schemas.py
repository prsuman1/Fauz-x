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


# Separate Endpoint Response Models
class MatchOnlyResponse(BaseModel):
    """Response for /api/match endpoint (match only, no MCQ)"""
    success: bool
    message: Optional[str] = None
    match_result: Optional[MatchResult] = None
    cv_filename: Optional[str] = None
    jd_title: Optional[str] = None


class GenerateMCQResponse(BaseModel):
    """Response for /api/generate-mcq endpoint"""
    success: bool
    message: Optional[str] = None
    mcq_test: Optional[MCQTestForFrontend] = None
    session_id: Optional[str] = None
    jd_title: Optional[str] = None
    cv_filename: Optional[str] = None


class MCQAnswersResponse(BaseModel):
    """Response for /api/get-mcq-answers endpoint"""
    success: bool
    session_id: str
    answers: Dict[int, str]  # {question_id: correct_answer}


class SessionInfo(BaseModel):
    """Response for /api/session-info endpoint"""
    session_id: str
    created_at: str
    jd_title: Optional[str] = None
    cv_filename: Optional[str] = None
    question_count: int
    role_type: Optional[str] = None


class SessionListResponse(BaseModel):
    """Response for listing sessions"""
    success: bool
    sessions: List[SessionInfo]


# Capabilities Generation Models
class JDDetailsForCapabilities(BaseModel):
    """JD Details input for capabilities generation (without capabilities)"""
    icon: Optional[str] = None
    title: str
    skills: List[str]
    niceToHave: Optional[List[str]] = []
    demandLevel: Optional[str] = None
    description: Optional[str] = ""
    responsibilities: Optional[List[str]] = []


class GenerateCapabilitiesRequest(BaseModel):
    """Request for /api/generate-capabilities endpoint"""
    jd_details: JDDetailsForCapabilities


class GenerateCapabilitiesResponse(BaseModel):
    """Response for /api/generate-capabilities endpoint"""
    success: bool
    message: Optional[str] = None
    jd_title: str
    role_type: str
    capabilities: List[str]


# Code Check Models
class ScoreBreakdown(BaseModel):
    """Breakdown of scores by category"""
    functionality: int = Field(ge=0, le=100)
    completeness: int = Field(ge=0, le=100)
    code_quality: int = Field(ge=0, le=100)
    best_practices: int = Field(ge=0, le=100)
    performance: int = Field(ge=0, le=100)


class CodeEvaluationResult(BaseModel):
    """Result of code evaluation"""
    passed: bool
    summary: str
    max_score: int = 100
    overall_score: float = Field(ge=0, le=100)
    score_breakdown: ScoreBreakdown
    strengths: List[str] = Field(default_factory=list)
    code_issues: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    confidence_level: float = Field(ge=0, le=1)
    processing_time: Optional[float] = None


class EvaluateCodeRequest(BaseModel):
    """Request for /api/evaluate-code endpoint"""
    candidate_id: str
    question: str
    answer_files: Dict[str, str]  # {"/filename.js": "code content"}
    sandbox_link: Optional[str] = None


class EvaluateCodeResponse(BaseModel):
    """Response for /api/evaluate-code endpoint"""
    success: bool
    message: Optional[str] = None
    candidate_id: str
    evaluation_result: Optional[CodeEvaluationResult] = None
    total_score: Optional[float] = None


# ============================
# Match V2 Models (DB-backed)
# ============================

class MatchV2Request(BaseModel):
    """Request for /api/match v2 endpoint"""
    jd_id: str
    candidate_id: str


class CapabilityScore(BaseModel):
    """Individual capability evaluation"""
    id: int
    skill: str
    expectedLevel: str = "intermediate"
    candidateLevel: str = "none"
    score: int = Field(ge=0, le=10)
    evidence: str = ""
    meetsRequirement: bool = False


class SkillCategory(BaseModel):
    """Group of capabilities under a category"""
    category: str
    score: float = 0
    weight: float = 0
    capabilities: List[CapabilityScore] = Field(default_factory=list)


class EvaluationSection(BaseModel):
    """Top-level evaluation section"""
    score: float = 0
    weight: float = 0
    weightedContribution: float = 0
    categories: List[SkillCategory] = Field(default_factory=list)


class NiceToHaveMatched(BaseModel):
    """A matched nice-to-have skill"""
    skill: str
    evidence: str = ""
    bonusPoints: float = 0


class NiceToHaves(BaseModel):
    """Nice-to-have skills evaluation"""
    matched: List[NiceToHaveMatched] = Field(default_factory=list)
    missing: List[str] = Field(default_factory=list)


class MatchV2Summary(BaseModel):
    """Summary of match evaluation"""
    totalRequirements: int = 0
    requirementsMetFully: int = 0
    requirementsMetPartially: int = 0
    requirementsMissing: int = 0
    matchPercentage: float = 0
    strengths: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    criticalMatches: List[str] = Field(default_factory=list)
    criticalGaps: List[str] = Field(default_factory=list)
    trainableWithin3Months: List[str] = Field(default_factory=list)


class HiringDecision(BaseModel):
    """Hiring decision details"""
    thresholdMet: bool = False
    scoreRange: str = ""
    rating: str = ""
    recommendation: str = ""
    confidence: str = "medium"
    rationale: str = ""


class MatchV2Result(BaseModel):
    """Full match v2 result"""
    position: str = ""
    candidateName: str = ""
    overallScore: float = 0
    evaluationCriteria: Dict[str, EvaluationSection] = Field(default_factory=dict)
    niceToHaves: Optional[NiceToHaves] = None
    summary: Optional[MatchV2Summary] = None
    hiringDecision: Optional[HiringDecision] = None
    analysisTimestamp: Optional[str] = None
    capabilityFile: Optional[str] = None
    domainMismatch: bool = False


class MatchV2Response(BaseModel):
    """Response for /api/match v2 endpoint"""
    success: bool
    message: Optional[str] = None
    result: Optional[MatchV2Result] = None
