import csv
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import MATCH_LOG_FILE
from app.models.schemas import MatchResult, MCQResult


class MatchLogger:
    """Service for logging match results to CSV."""

    def __init__(self, log_file: Optional[Path] = None):
        self.log_file = log_file or MATCH_LOG_FILE
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Ensure the log file exists with headers."""
        if not self.log_file.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp",
                    "cv_filename",
                    "jd_title",
                    "match_score",
                    "match_grade",
                    "skill_match_percentage",
                    "matched_skills_count",
                    "missing_skills_count",
                    "domain_match",
                    "experience_type",
                    "recommendation",
                    "mcq_score",
                    "mcq_passed",
                    "summary",
                ])

    def log_match(
        self,
        cv_filename: str,
        jd_title: str,
        match_result: MatchResult,
        mcq_result: Optional[MCQResult] = None,
    ):
        """
        Log a match result to the CSV file.

        Args:
            cv_filename: Name of the CV file
            jd_title: Title of the job description
            match_result: The match analysis result
            mcq_result: Optional MCQ test result
        """
        with open(self.log_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now().isoformat(),
                cv_filename,
                jd_title,
                match_result.score,
                match_result.grade.value,
                match_result.skill_analysis.skill_match_percentage,
                len(match_result.skill_analysis.matched_required),
                len(match_result.skill_analysis.missing_required),
                match_result.experience_analysis.domain_match,
                match_result.experience_analysis.experience_type,
                match_result.recommendation,
                mcq_result.score_percentage if mcq_result else "",
                mcq_result.passed if mcq_result else "",
                match_result.summary[:200] if match_result.summary else "",
            ])

    def get_recent_logs(self, limit: int = 100) -> list:
        """
        Get recent log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of log entries as dictionaries
        """
        if not self.log_file.exists():
            return []

        entries = []
        with open(self.log_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                entries.append(row)

        # Return most recent entries
        return entries[-limit:]


# Singleton instance
_logger = None


def get_logger() -> MatchLogger:
    """Get or create the MatchLogger singleton."""
    global _logger
    if _logger is None:
        _logger = MatchLogger()
    return _logger
