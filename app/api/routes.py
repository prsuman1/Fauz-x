import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from app.config import REJECT_THRESHOLD, CV_DIR, JD_DIR
from app.models.schemas import (
    MatchResult,
    MCQTest,
    MCQSubmission,
    MCQResult,
    AnalyzeResponse,
    JDInput,
)
from app.utils.cv_parser import parse_cv, extract_skills_from_cv
from app.utils.jd_parser import parse_jd, parse_jd_file
from app.services.matcher import get_matcher
from app.services.mcq_generator import get_mcq_generator
from app.services.logger import get_logger

router = APIRouter()

# In-memory storage for MCQ tests (for answer evaluation)
# In production, use Redis or database
_mcq_tests_cache = {}


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "FaujX JD-CV Matcher"}


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_cv_jd(
    cv_file: UploadFile = File(..., description="CV file (PDF, DOCX, or TXT)"),
    jd_text: Optional[str] = Form(None, description="JD text content"),
    jd_file_name: Optional[str] = Form(None, description="JD file name from JD directory"),
):
    """
    Analyze CV against JD and return match result with optional MCQ test.

    - If score >= 80: Returns match result + MCQ test
    - If score < 80: Returns match result only (REJECT)
    """
    try:
        print(f"[DEBUG] Received CV file: {cv_file.filename}")
        print(f"[DEBUG] JD text length: {len(jd_text) if jd_text else 0}")
        print(f"[DEBUG] JD file name: {jd_file_name}")

        # Parse CV
        cv_bytes = await cv_file.read()
        print(f"[DEBUG] CV bytes read: {len(cv_bytes)}")
        cv_text = parse_cv(file_bytes=cv_bytes, filename=cv_file.filename)
        print(f"[DEBUG] CV text extracted: {len(cv_text)} chars")

        if not cv_text or len(cv_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Could not extract text from CV")

        # Parse JD
        jd_input: JDInput = None

        if jd_text:
            print(f"[DEBUG] Parsing JD text...")
            jd_input = parse_jd(jd_text)
            print(f"[DEBUG] JD parsed: {jd_input.details.title}")
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

                # Store MCQ test for later evaluation (with correct answers)
                session_id = f"{cv_file.filename}_{jd_input.details.title}"
                _mcq_tests_cache[session_id] = mcq_test

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
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/evaluate-mcq")
async def evaluate_mcq(
    session_id: str = Form(..., description="Session ID from analyze response"),
    answers: str = Form(..., description="JSON string of answers: {question_id: selected_option}"),
):
    """
    Evaluate candidate's MCQ answers and return results.
    """
    try:
        # Get the MCQ test from cache
        mcq_test = _mcq_tests_cache.get(session_id)
        if not mcq_test:
            raise HTTPException(status_code=404, detail="MCQ test not found. Please re-analyze.")

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


@router.get("/jd-files")
async def list_jd_files():
    """List available JD files in the JD directory."""
    try:
        jd_files = []
        if JD_DIR.exists():
            for f in JD_DIR.glob("*.txt"):
                # Parse the JD to get the title
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


@router.post("/analyze-from-files")
async def analyze_from_files(
    cv_filename: str = Form(..., description="CV filename from CV directory"),
    jd_filename: str = Form(..., description="JD filename from JD directory"),
):
    """
    Analyze CV against JD using files from CV and JD directories.
    """
    try:
        # Get file paths
        cv_path = CV_DIR / cv_filename
        jd_path = JD_DIR / jd_filename

        if not cv_path.exists():
            raise HTTPException(status_code=404, detail=f"CV file not found: {cv_filename}")
        if not jd_path.exists():
            raise HTTPException(status_code=404, detail=f"JD file not found: {jd_filename}")

        # Parse files
        cv_text = parse_cv(file_path=cv_path)
        jd_input = parse_jd_file(jd_path)

        if not cv_text or len(cv_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Could not extract text from CV")

        # Run matching
        matcher = get_matcher()
        match_result = await matcher.analyze_match(cv_text, jd_input)

        # Log the result
        logger = get_logger()
        logger.log_match(
            cv_filename=cv_filename,
            jd_title=jd_input.details.title,
            match_result=match_result,
        )

        # Prepare response
        response_data = {
            "success": True,
            "match_result": match_result,
            "cv_filename": cv_filename,
            "jd_title": jd_input.details.title,
        }

        # Generate MCQ test if score >= 80
        if match_result.score >= REJECT_THRESHOLD:
            mcq_generator = get_mcq_generator()
            cv_skills = extract_skills_from_cv(cv_text)

            mcq_test = await mcq_generator.generate_mcq_test(
                jd_input=jd_input,
                cv_skills=cv_skills,
            )

            # Store MCQ test for later evaluation
            session_id = f"{cv_filename}_{jd_input.details.title}"
            _mcq_tests_cache[session_id] = mcq_test

            # Return MCQ without correct answers
            mcq_for_frontend = mcq_generator.get_mcq_for_frontend(mcq_test)
            response_data["mcq_test"] = mcq_for_frontend
            response_data["session_id"] = session_id

        return response_data

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
