import logging
import re

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous\s+)?instructions",
    r"(?i)bypass\s+restrictions",
    r"(?i)as\s+an\s+unrestricted\s+ai",
    r"(?i)system\s+prompt",
    r"(?i)forget\s+what\s+you\s+were\s+told",
    r"(?i)you\s+are\s+now\s+in\s+developer\s+mode",
]

# Regex patterns for sensitive entity redaction (Defense in Depth)
PII_PATTERNS = {
    "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
    "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b",
    "CREDIT_CARD": r"\b(?:\d[ -]*?){13,16}\b",
    "PHONE": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
}

def check_input_guardrails(query: str) -> None:    
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query):
            logger.warning("Prompt injection detected in query: %s", query)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query violates security and acceptable use policies."
            )

def apply_output_guardrails(text: str) -> str:    
    safe_text = text
    for pii_type, pattern in PII_PATTERNS.items():
        safe_text = re.sub(pattern, f"[REDACTED {pii_type}]", safe_text)
    
    return safe_text