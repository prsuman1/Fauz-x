import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from app.config import REJECT_THRESHOLD, CV_DIR, JD_DIR
from app.models.schemas import (
    MatchResult,
    MCQTest,
    MCQSubmission,
    MCQResult,
    AnalyzeResponse,
    MatchOnlyResponse,
    GenerateMCQResponse,
    MCQAnswersResponse,
    SessionInfo,
    JDInput,
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
from app.utils.cv_parser import parse_cv, extract_skills_from_cv
from app.utils.jd_parser import parse_jd, parse_jd_file
from app.services.matcher import get_matcher
from app.services.match_v2 import get_matcher_v2
from app.services.mcq_generator import get_mcq_generator
from app.services.logger import get_logger
from app.services.capabilities_generator import get_capabilities_generator
from app.services.code_evaluator import get_code_evaluator
from app.services.api_key_manager import get_api_key_manager

router = APIRouter()

# Enhanced in-memory storage for sessions
# Structure: {session_id: {mcq_test, created_at, jd_title, cv_filename, jd_text, cv_text}}
_sessions_cache: Dict[str, Dict[str, Any]] = {}


def _generate_session_id(cv_filename: str, jd_title: str) -> str:
    """Generate a unique session ID."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{cv_filename}_{jd_title}_{timestamp}"


def _store_session(
    session_id: str,
    mcq_test: MCQTest,
    jd_title: str,
    cv_filename: str,
    jd_text: str = None,
    cv_text: str = None,
) -> None:
    """Store session data in cache."""
    _sessions_cache[session_id] = {
        "mcq_test": mcq_test,
        "created_at": datetime.now().isoformat(),
        "jd_title": jd_title,
        "cv_filename": cv_filename,
        "jd_text": jd_text,
        "cv_text": cv_text,
    }


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

    Takes candidate_id, question, answer_files (code), and optional sandbox_link.
    Returns detailed evaluation with score breakdown.
    """
    try:
        evaluator = get_code_evaluator()
        result = await evaluator.evaluate_code(request)

        return EvaluateCodeResponse(
            success=True,
            candidate_id=request.candidate_id,
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
# Retrieve MCQs Endpoint
# ====================

@router.get("/retrieve-mcqs/{session_id}")
async def retrieve_mcqs(session_id: str):
    """
    Retrieve MCQ test for a session (without correct answers).

    Use this to re-fetch MCQ questions for a previously generated test.
    """
    session = _sessions_cache.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    mcq_test: MCQTest = session["mcq_test"]
    mcq_generator = get_mcq_generator()
    mcq_for_frontend = mcq_generator.get_mcq_for_frontend(mcq_test)

    return {
        "success": True,
        "session_id": session_id,
        "mcq_test": mcq_for_frontend,
        "jd_title": session.get("jd_title"),
        "cv_filename": session.get("cv_filename"),
    }


# ====================
# Session Management Endpoints
# ====================

@router.post("/reset-session")
async def reset_session(session_id: str = Form(..., description="Session ID to reset")):
    """
    Reset/delete a session from cache.
    """
    if session_id in _sessions_cache:
        del _sessions_cache[session_id]
        return {"success": True, "message": f"Session {session_id} has been reset"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/session-info/{session_id}", response_model=SessionInfo)
async def get_session_info(session_id: str):
    """
    Get information about a session.
    """
    session = _sessions_cache.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    mcq_test: MCQTest = session["mcq_test"]

    return SessionInfo(
        session_id=session_id,
        created_at=session.get("created_at", ""),
        jd_title=session.get("jd_title"),
        cv_filename=session.get("cv_filename"),
        question_count=mcq_test.total_questions,
        role_type=mcq_test.role_type,
    )


@router.get("/sessions")
async def list_sessions():
    """
    List all active sessions.
    """
    sessions = []
    for session_id, session in _sessions_cache.items():
        mcq_test: MCQTest = session["mcq_test"]
        sessions.append({
            "session_id": session_id,
            "created_at": session.get("created_at", ""),
            "jd_title": session.get("jd_title"),
            "cv_filename": session.get("cv_filename"),
            "question_count": mcq_test.total_questions,
            "role_type": mcq_test.role_type,
        })

    return {"success": True, "sessions": sessions}


# ====================
# Evaluate MCQ Endpoint
# ====================

@router.post("/evaluate-mcq")
async def evaluate_mcq(
    session_id: str = Form(..., description="Session ID from analyze response"),
    answers: str = Form(..., description="JSON string of answers: {question_id: selected_option}"),
):
    """
    Evaluate candidate's MCQ answers and return results.
    """
    try:
        # Get the session from cache
        session = _sessions_cache.get(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="MCQ test not found. Please re-generate.")

        mcq_test: MCQTest = session["mcq_test"]

        # Parse answers
        try:
            answers_dict = json.loads(answers)
            # Convert string keys to int
            answers_dict = {int(k): v for k, v in answers_dict.items()}
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid answers format")

        # Evaluate
        mcq_generator = get_mcq_generator()
        result = mcq_generator.evaluate_mcq(mcq_test, answers_dict)

        return {
            "success": True,
            "result": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {str(e)}")


# ====================
# Combined Analyze Endpoint (Legacy/Convenience)
# ====================

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_cv_jd(
    cv_file: UploadFile = File(..., description="CV file (PDF, DOCX, or TXT)"),
    jd_text: Optional[str] = Form(None, description="JD text content"),
    jd_file_name: Optional[str] = Form(None, description="JD file name from JD directory"),
):
    """
    Analyze CV against JD and return match result with optional MCQ test.

    This is a combined endpoint that does both matching and MCQ generation.
    - If score >= 80: Returns match result + MCQ test
    - If score < 80: Returns match result only (REJECT)
    """
    try:
        # Parse CV
        cv_bytes = await cv_file.read()
        cv_text = parse_cv(file_bytes=cv_bytes, filename=cv_file.filename)

        if not cv_text or len(cv_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Could not extract text from CV")

        # Parse JD
        jd_input: JDInput = None

        if jd_text:
            jd_input = parse_jd(jd_text)
        elif jd_file_name:
            jd_file_path = JD_DIR / jd_file_name
            if not jd_file_path.exists():
                raise HTTPException(status_code=404, detail=f"JD file not found: {jd_file_name}")
            jd_input = parse_jd_file(jd_file_path)
        else:
            raise HTTPException(status_code=400, detail="Either jd_text or jd_file_name must be provided")

        # Run matching
        matcher = get_matcher()
        match_result = await matcher.analyze_match(cv_text, jd_input)

        # Log the result
        logger = get_logger()
        logger.log_match(
            cv_filename=cv_file.filename,
            jd_title=jd_input.details.title,
            match_result=match_result,
        )

        # Prepare response
        response_data = {
            "success": True,
            "match_result": match_result,
            "cv_filename": cv_file.filename,
            "jd_title": jd_input.details.title,
        }

        # Generate MCQ test if score >= 80
        if match_result.score >= REJECT_THRESHOLD:
            try:
                mcq_generator = get_mcq_generator()

                # Extract skills from CV for MCQ
                cv_skills = extract_skills_from_cv(cv_text)

                mcq_test = await mcq_generator.generate_mcq_test(
                    jd_input=jd_input,
                    cv_skills=cv_skills,
                )

                # Store session with enhanced data
                session_id = _generate_session_id(cv_file.filename, jd_input.details.title)
                _store_session(
                    session_id=session_id,
                    mcq_test=mcq_test,
                    jd_title=jd_input.details.title,
                    cv_filename=cv_file.filename,
                    jd_text=jd_text,
                    cv_text=cv_text,
                )

                # Return MCQ without correct answers
                mcq_for_frontend = mcq_generator.get_mcq_for_frontend(mcq_test)
                response_data["mcq_test"] = mcq_for_frontend
                response_data["session_id"] = session_id
            except Exception as mcq_error:
                # Log MCQ generation error but don't fail the request
                print(f"MCQ generation failed: {mcq_error}")
                response_data["mcq_error"] = "MCQ generation temporarily unavailable"

        return response_data

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


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
