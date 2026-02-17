from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator
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
    coding_assignment_id: str
    files: Dict[str, str]  # {"/filename.js": "code content"}
    max_score: int = 100


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


# ============================
# MCQ V2 Models (DB-backed)
# ============================

class GenerateMCQV2Request(BaseModel):
    """Request for DB-backed /api/generate-mcq endpoint"""
    jd_id: str
    candidate_id: str
    domain: str
    num_questions: int = Field(default=20, ge=5, le=50)
    difficulty_mix: Dict[str, float] = Field(
        default={"easy": 0.3, "medium": 0.5, "hard": 0.2}
    )

    @model_validator(mode="after")
    def validate_difficulty_mix(self):
        valid_keys = {"easy", "medium", "hard"}
        if not set(self.difficulty_mix.keys()).issubset(valid_keys):
            raise ValueError(f"difficulty_mix keys must be from {valid_keys}")
        total = sum(self.difficulty_mix.values())
        if not (0.95 <= total <= 1.05):
            raise ValueError(f"difficulty_mix values must sum to ~1.0, got {total}")
        return self


class MCQV2Question(BaseModel):
    """Single MCQ question in V2 format (full, with answers — for internal use)"""
    question_id: int
    type: str = "single_choice"
    difficulty: str
    question: str
    domain: str
    skill_tags: List[str] = Field(default_factory=list)
    options: List[str]  # 4 full-text strings
    correct_answer: str  # A/B/C/D (primary, for single_choice)
    correct_answers: List[str] = Field(default_factory=list)  # ["B"] or ["A","C"] for multiple
    explanation: str = ""
    source: str = "llm_generated"


class MCQV2QuestionForFrontend(BaseModel):
    """MCQ question stripped of answers — returned to frontend"""
    question_id: int
    type: str = "single_choice"
    difficulty: str
    question: str
    skill_tags: List[str] = Field(default_factory=list)
    options: List[str]


class MCQV2Metadata(BaseModel):
    """Metadata for MCQ V2 response"""
    role_id: str
    skills: List[str] = Field(default_factory=list)
    candidate_id: str
    skills_count: int = 0
    total_questions: int
    session_id: str


class GenerateMCQV2Response(BaseModel):
    """Response for DB-backed /api/generate-mcq endpoint"""
    success: bool
    message: Optional[str] = None
    questions: List[MCQV2QuestionForFrontend] = Field(default_factory=list)
    metadata: Optional[MCQV2Metadata] = None


class GetMCQAnswersRequest(BaseModel):
    """Request for /api/get-mcq-answers endpoint"""
    session_id: str


class MCQAnswerDetail(BaseModel):
    """Single answer detail for get-mcq-answers response"""
    question_id: int
    question: str
    correct_answer: str
    correct_answers: List[str] = Field(default_factory=list)
    explanation: str = ""
    type: str = "single_choice"


class GetMCQAnswersResponse(BaseModel):
    """Response for /api/get-mcq-answers endpoint"""
    success: bool
    answers: List[MCQAnswerDetail] = Field(default_factory=list)


# ============================
# Coding Assignment Models
# ============================

class GenerateCodingAssignmentRequest(BaseModel):
    """Request for /api/generate-coding-assignment endpoint"""
    jd_id: str
    candidate_id: str
    num_assignments: int = Field(default=1, ge=1, le=5)


class CodingAssignmentExample(BaseModel):
    """Single example for a coding assignment"""
    input: str
    output: str
    explanation: str = ""


class CodingAssignmentTestCase(BaseModel):
    """Single test case for a coding assignment"""
    input: str
    expected_output: str
    description: str = ""
    is_hidden: bool = False


class CodingAssignment(BaseModel):
    """A single coding assignment"""
    coding_assignment_id: Optional[str] = None
    assignment_id: int
    title: str
    problem_statement: str
    difficulty: str = "medium"
    category: str = ""
    input_format: str = ""
    output_format: str = ""
    constraints: List[str] = Field(default_factory=list)
    examples: List[CodingAssignmentExample] = Field(default_factory=list)
    test_cases: List[CodingAssignmentTestCase] = Field(default_factory=list)
    starter_code: Dict[str, str] = Field(default_factory=dict)
    solution_approach: str = ""
    time_complexity: str = ""
    space_complexity: str = ""
    skills_tested: List[str] = Field(default_factory=list)
    estimated_time_minutes: int = 30
    hints: List[str] = Field(default_factory=list)


class CodingAssignmentMetadata(BaseModel):
    """Metadata about the candidate and JD"""
    candidate_name: str = ""
    candidate_email: Optional[str] = None
    candidate_skills: List[str] = Field(default_factory=list)
    current_role: Optional[str] = None


class GenerateCodingAssignmentResponse(BaseModel):
    """Response for /api/generate-coding-assignment endpoint"""
    success: bool
    message: Optional[str] = None
    total_assignments: int = 0
    assignments: List[CodingAssignment] = Field(default_factory=list)
    job_title: str = ""
    jd_source: str = "database"
    generation_timestamp: str = ""
    metadata: Optional[CodingAssignmentMetadata] = None
    total_estimated_time_minutes: int = 0
    difficulty_distribution: Dict[str, int] = Field(default_factory=dict)
    skills_coverage: List[str] = Field(default_factory=list)
