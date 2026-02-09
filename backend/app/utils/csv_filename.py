"""
Production-safe CSV filename generation for batch and single-feature exports.

Generates short, unique, OS-safe filenames. Never use raw user input in filenames.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Optional

# Max length for sanitized feature name (keeps total filename under 60 chars).
MAX_FEATURE_NAME_LENGTH: int = 30


def sanitize_feature_name(name: str) -> str:
    """
    Sanitize user input for use in filenames. Never use raw user input in filenames.

    Rules: lowercase, replace non-alphanumeric with underscore, allow only a-z 0-9 _,
    truncate to MAX_FEATURE_NAME_LENGTH, strip leading/trailing underscores.
    """
    if not name or not isinstance(name, str):
        return ""
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = s.strip("_")
    return s[:MAX_FEATURE_NAME_LENGTH]


def generate_csv_filename(feature_name: Optional[str] = None) -> str:
    """
    Generate a short, unique, OS-safe CSV filename.

    - If feature_name is None → batch export: tc_<YYYYMMDD_HHMMSS>_<shortHash>.csv
    - If feature_name is provided → feature export: tc_<sanitizedFeatureName>_<YYYYMMDD_HHMMSS>_<shortHash>.csv

    Timestamp: server time, YYYYMMDD_HHMMSS.
    Short hash: first 6 hex chars of UUID v4 (uniqueness for rapid exports).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    short_hash = uuid.uuid4().hex[:6]

    if feature_name:
        safe_name = sanitize_feature_name(feature_name)
        if not safe_name:
            return f"tc_{timestamp}_{short_hash}.csv"
        return f"tc_{safe_name}_{timestamp}_{short_hash}.csv"
    return f"tc_{timestamp}_{short_hash}.csv"
