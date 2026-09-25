import os
import json
import logging
import yaml
from typing import Dict, List, Any


def setup_logger(log_file: str = "redaction.log") -> logging.Logger:
    """Configures and returns a logger instance writing to both console and log file."""
    logger = logging.getLogger("PIIRedactor")
    logger.setLevel(logging.INFO)
    logger.handlers = []  # Clear existing handlers to prevent duplicates

    # Console Handler
    c_handler = logging.StreamHandler()
    c_handler.setLevel(logging.INFO)
    c_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    c_handler.setFormatter(c_format)
    logger.addHandler(c_handler)

    # File Handler
    try:
        f_handler = logging.FileHandler(log_file, encoding='utf-8')
        f_handler.setLevel(logging.INFO)
        f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        f_handler.setFormatter(f_format)
        logger.addHandler(f_handler)
    except Exception as e:
        logger.warning(f"Could not initialize log file handler: {e}")

    return logger


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Loads configuration settings from YAML file."""
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


def save_json(data: Any, filepath: str) -> None:
    """Saves data dictionary to a JSON file formatted neatly."""
    os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def resolve_overlaps(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Resolves overlapping span matches.
    Prioritizes matches based on confidence score, entity priority, and span length.
    """
    if not matches:
        return []

    # Sort matches by start position, then by length descending, then by confidence descending
    sorted_matches = sorted(
        matches,
        key=lambda x: (x["start"], -(x["end"] - x["start"]), -x.get("confidence", 0.5))
    )

    resolved = []
    for match in sorted_matches:
        start, end = match["start"], match["end"]
        overlap = False
        for prev in resolved:
            p_start, p_end = prev["start"], prev["end"]
            # Check if current match overlaps with previous resolved match
            if max(start, p_start) < min(end, p_end):
                overlap = True
                # If current match is a high-priority regex (EMAIL, PHONE, PAN, SSN) and prev is generic NER, swap
                if match.get("source") == "regex" and prev.get("source") != "regex":
                    if match.get("entity_type") in ["EMAIL", "PHONE", "PAN", "SSN", "IP_ADDRESS"]:
                        resolved.remove(prev)
                        resolved.append(match)
                break
        if not overlap and match not in resolved:
            resolved.append(match)

    # Final sort by start index
    resolved.sort(key=lambda x: x["start"])
    return resolved
