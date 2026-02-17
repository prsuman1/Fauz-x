from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.config import CV_DIR, JD_DIR
from app.models.schemas import (
    GenerateCapabilitiesRequest,
    GenerateCapabilitiesResponse,
    EvaluateCodeRequest,
    EvaluateCodeResponse,
    MatchV2Request,
    MatchV2Response,
    GenerateMCQV2Request,
    GenerateMCQV2Response,
    MCQV2Metadata,
    MCQV2QuestionForFrontend,
    GetMCQAnswersRequest,
    GetMCQAnswersResponse,
    MCQAnswerDetail,
    GenerateCodingAssignmentRequest,
    GenerateCodingAssignmentResponse,
)
from app.utils.jd_parser import parse_jd_file
from app.services.match_v2 import get_matcher_v2
from app.services.mcq_generator import get_mcq_generator
from app.services.capabilities_generator import get_capabilities_generator
from app.services.code_evaluator import get_code_evaluator
from app.services.api_key_manager import get_api_key_manager

router = APIRouter()


# ====================
# Health Check
# ====================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "FaujX JD-CV Matcher"}


# ====================
# API Key Status (Debug)
# ====================

@router.get("/key-status")
async def key_status():
    """Return status of all API keys (masked) with request counts, cooldown, and in-flight info."""
    manager = get_api_key_manager()
    keys = manager.get_status()
    available = sum(1 for k in keys if k["status"] == "available")
    idle = sum(1 for k in keys if k["status"] == "available" and k["in_flight_count"] == 0)
    busy = sum(1 for k in keys if k["in_flight_count"] > 0)
    total_in_flight = sum(k["in_flight_count"] for k in keys)
    return {
        "total_keys": len(keys),
        "available_keys": available,
        "rate_limited_keys": len(keys) - available,
        "idle_keys": idle,
        "busy_keys": busy,
        "total_in_flight_requests": total_in_flight,
        "keys": keys,
    }


# ====================
# Generate Capabilities Endpoint
# ====================

@router.post("/generate-capabilities", response_model=GenerateCapabilitiesResponse)
async def generate_capabilities(request: GenerateCapabilitiesRequest):
    """
    Generate capabilities from JD Details using AI.

    Takes JD Details JSON (title, skills, niceToHave, description, responsibilities)
    and generates a comprehensive list of testable capabilities.
    """
    try:
        generator = get_capabilities_generator()
        result = await generator.generate_capabilities(request.jd_details)

        return GenerateCapabilitiesResponse(
            success=True,
            jd_title=result["jd_title"],
            role_type=result["role_type"],
            capabilities=result["capabilities"],
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Capabilities generation failed: {str(e)}")


# ====================
# Code Evaluation Endpoint
# ====================

@router.post("/evaluate-code", response_model=EvaluateCodeResponse)
async def evaluate_code(request: EvaluateCodeRequest):
    """
    Evaluate candidate code submission using AI.

    Takes coding_assignment_id, files (code), and optional max_score.
    Fetches the assignment question from the database and returns detailed evaluation.
    """
    try:
        evaluator = get_code_evaluator()
        result, candidate_id = await evaluator.evaluate_code(request)

        return EvaluateCodeResponse(
            success=True,
            candidate_id=candidate_id,
            evaluation_result=result,
            total_score=result.overall_score,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code evaluation failed: {str(e)}")


# ====================
# Match Only Endpoint
# ====================

@router.post("/match", response_model=MatchV2Response)
async def match_cv_jd(request: MatchV2Request):
    """
    Match a candidate against a JD using DB-backed data.

    Accepts JSON body with jd_id (role_id) and candidate_id.
    Returns capability-level evaluation with hiring decision.
    """
    try:
        matcher = get_matcher_v2()
        result = await matcher.match(request.jd_id, request.candidate_id)

        return MatchV2Response(success=True, result=result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Match failed: {str(e)}")


# ====================
# Generate MCQ Endpoint
# ====================

@router.post("/generate-mcq", response_model=GenerateMCQV2Response)
async def generate_mcq(request: GenerateMCQV2Request):
    """
    Generate MCQ test based on role skills/capabilities and candidate data from DB.

    Accepts JSON body with jd_id (role_id), candidate_id, domain, num_questions,
    and difficulty_mix. Returns questions WITHOUT answers (stored in mcq_database).
    Use /get-mcq-answers with session_id to retrieve answers later.
    """
    try:
        mcq_generator = get_mcq_generator()
        questions, role_title, session_id, candidate_name, role_skills = (
            await mcq_generator.generate_mcq_v2(request)
        )

        # Strip answers — return only frontend-safe fields
        frontend_questions = [
            MCQV2QuestionForFrontend(
                question_id=q.question_id,
                type=q.type,
                difficulty=q.difficulty,
                question=q.question,
                skill_tags=q.skill_tags,
                options=q.options,
            )
            for q in questions
        ]

        return GenerateMCQV2Response(
            success=True,
            message=f"{len(questions)} questions generated",
            questions=frontend_questions,
            metadata=MCQV2Metadata(
                role_id=request.jd_id,
                skills=role_skills,
                candidate_id=request.candidate_id,
                skills_count=len(role_skills),
                total_questions=len(questions),
                session_id=session_id,
            ),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MCQ generation failed: {str(e)}")


# ====================
# Generate Coding Assignment Endpoint
# ====================

@router.post("/generate-coding-assignment", response_model=GenerateCodingAssignmentResponse)
async def generate_coding_assignment(request: GenerateCodingAssignmentRequest):
    """
    Generate tailored coding assignments for a candidate.

    Performs smart capability selection — checks which skills were already tested
    via MCQ and targets the untested gaps. Stores results in mcq_database.
    """
    from app.services.coding_assignment_generator import get_coding_assignment_generator

    try:
        generator = get_coding_assignment_generator()
        return await generator.generate_coding_assignment(request)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Coding assignment generation failed: {str(e)}")


# ====================
# Get MCQ Answers Endpoint
# ====================

@router.post("/get-mcq-answers", response_model=GetMCQAnswersResponse)
async def get_mcq_answers(request: GetMCQAnswersRequest):
    """
    Get correct answers + explanations for an MCQ session from mcq_database.

    Accepts JSON body with session_id.
    Returns answers with explanations for each question.
    """
    from uuid import UUID as _UUID
    from app.db import get_mcq_db_pool
    from app.db.mcq_queries import fetch_mcq_answers_by_session

    try:
        session_uuid = _UUID(request.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format")

    try:
        mcq_pool = await get_mcq_db_pool()
        rows = await fetch_mcq_answers_by_session(mcq_pool, session_uuid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    if rows is None:
        raise HTTPException(status_code=404, detail="Session not found or has no questions")

    answer_details = [
        MCQAnswerDetail(
            question_id=r["question_id"],
            question=r["question"],
            correct_answer=r["correct_answer"],
            correct_answers=r["correct_answers"],
            explanation=r["explanation"],
            type=r["type"],
        )
        for r in rows
    ]

    return GetMCQAnswersResponse(
        success=True,
        answers=answer_details,
    )


# ====================
# File Listing Endpoints
# ====================

@router.get("/jd-files")
async def list_jd_files():
    """List available JD files in the JD directory."""
    try:
        jd_files = []
        if JD_DIR.exists():
            for f in JD_DIR.glob("*.txt"):
                try:
                    jd_input = parse_jd_file(f)
                    jd_files.append({
                        "filename": f.name,
                        "title": jd_input.details.title,
                        "skills_count": len(jd_input.details.skills),
                    })
                except Exception:
                    jd_files.append({
                        "filename": f.name,
                        "title": f.stem,
                        "skills_count": 0,
                    })

        return {"success": True, "jd_files": jd_files}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cv-files")
async def list_cv_files():
    """List available CV files in the CV directory."""
    try:
        cv_files = []
        if CV_DIR.exists():
            for ext in ["*.pdf", "*.docx", "*.txt"]:
                for f in CV_DIR.glob(ext):
                    cv_files.append({
                        "filename": f.name,
                        "size_kb": round(f.stat().st_size / 1024, 2),
                    })

        return {"success": True, "cv_files": cv_files}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
