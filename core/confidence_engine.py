
from __future__ import annotations

from typing import Any


class ConfidenceEngine:
    """
    Handles confidence categorisation, per-issue enrichment,
    and aggregate scan-level statistics.
    """

    HIGH_THRESHOLD   = 80
    MEDIUM_THRESHOLD = 50

    SEVERITY_WEIGHT: dict[str, int] = {
        "critical": 10,
        "high":      6,
        "medium":    3,
        "low":       1,
    }

    # label helpers

    @staticmethod
    def get_confidence_label(score: int) -> str:
        if score >= ConfidenceEngine.HIGH_THRESHOLD:
            return "High Confidence"
        if score >= ConfidenceEngine.MEDIUM_THRESHOLD:
            return "Medium Confidence"
        return "VERIFY THIS REVIEW"

    @staticmethod
    def get_confidence_color(score: int) -> str:
        if score >= ConfidenceEngine.HIGH_THRESHOLD:
            return "green"
        if score >= ConfidenceEngine.MEDIUM_THRESHOLD:
            return "orange"
        return "red"

    @staticmethod
    def get_severity_emoji(severity: str) -> str:
        return {
            "critical": "🔴",
            "high":     "🟠",
            "medium":   "🟡",
            "low":      "🟢",
        }.get(severity.lower(), "⚪")

    # ── per-issue enrichment

    @staticmethod
    def enrich_issue(issue: dict[str, Any]) -> dict[str, Any]:
        """Attach label, color, and emoji fields to a single issue dict."""
        score = issue.get("confidence_score", 0)
        issue["confidence_label"] = ConfidenceEngine.get_confidence_label(score)
        issue["confidence_color"] = ConfidenceEngine.get_confidence_color(score)
        issue["severity_emoji"]   = ConfidenceEngine.get_severity_emoji(
            issue.get("severity", "")
        )
        return issue

    # batch processing 

    @staticmethod
    def process_reviews(review_data: dict[str, Any]) -> dict[str, Any]:
        """
        Enrich every issue and attach a ``summary`` dict to review_data:

        summary = {
            total, by_severity, by_confidence,
            avg_confidence, risk_score
        }
        """
        issues: list[dict] = review_data.get("issues", [])

        sev_counts  = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        conf_counts = {
            "High Confidence": 0,
            "Medium Confidence": 0,
            "VERIFY THIS REVIEW": 0,
        }
        total_conf = 0
        risk       = 0

        for issue in issues:
            ConfidenceEngine.enrich_issue(issue)

            sev = issue.get("severity", "low").lower()
            sev_counts[sev] = sev_counts.get(sev, 0) + 1
            risk += ConfidenceEngine.SEVERITY_WEIGHT.get(sev, 0)

            lbl = issue["confidence_label"]
            conf_counts[lbl] = conf_counts.get(lbl, 0) + 1
            total_conf += issue.get("confidence_score", 0)

        review_data["summary"] = {
            "total":          len(issues),
            "by_severity":    sev_counts,
            "by_confidence":  conf_counts,
            "avg_confidence": round(total_conf / len(issues), 1) if issues else 0.0,
            "risk_score":     risk,
        }
        return review_data
