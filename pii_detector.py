import re
import logging
from typing import List, Dict, Any, Optional
import spacy

try:
    from presidio_analyzer import AnalyzerEngine
    HAS_PRESIDIO = True
except ImportError:
    HAS_PRESIDIO = False

from utils import resolve_overlaps, load_config

logger = logging.getLogger("PIIRedactor")


class PIIDetector:
    """
    Hybrid PII Detector using spaCy NER, Microsoft Presidio Analyzer,
    and optimized Regular Expressions for high-precision entity extraction.
    """

    DEFAULT_REGEX_PATTERNS = {
        "EMAIL": r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',
        "PHONE": r'(?:\+91[- ]?)?[6-9]\d{9}|\b0\d{2,4}[- ]?\d{6,8}\b|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        "IP_ADDRESS": r'\b(?:\d{1,3}\.){3}\d{1,3}\b|\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',
        "CREDIT_CARD": r'\b(?:\d[ -]*?){13,16}\b',
        "SSN": r'\b\d{3}-\d{2}-\d{4}\b',
        "DATE_OF_BIRTH": r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b',
        "PAN": r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b',
        "AADHAAR": r'\b[2-9]\d{3}[ -]\d{4}[ -]\d{4}\b',
        "BANK_ACCOUNT": r'\b[0-9]{9,18}\b'
    }

    BOILERPLATE_EXCLUSIONS = {
        "RED HERRING PROSPECTUS", "COMPANIES ACT", "SEBI ICDR REGULATIONS",
        "BOOK BUILT OFFER", "TABLE OF CONTENTS", "GENERAL INFORMATION DOCUMENT",
        "CORPORATE IDENTITY NUMBER", "REGISTERED OFFICE", "CORPORATE OFFICE",
        "SECTION 32", "THE COMPANIES ACT", "ANCHOR INVESTORS", "BOARD OF DIRECTORS",
        "BID/OFFER CLOSING DAY", "BID/OFFER OPENING DAY", "OUR COMPANY", "PROSPECTUS",
        "SSN", "AADHAAR", "SERVER IP", "PAN", "IP", "EMAIL", "PHONE"
    }

    KNOWN_LOCATIONS = {"MAHARASHTRA", "MUMBAI", "PUNE", "DELHI", "BOMBAY", "INDIA", "VILLAGE BIRDEWADI"}

    def __init__(self, config_path: str = "config.yaml"):
        self.config = load_config(config_path)
        self.pipeline_cfg = self.config.get("pipeline", {})
        self.regex_patterns = self.config.get("regex_patterns", self.DEFAULT_REGEX_PATTERNS)
        self.spacy_model_name = self.pipeline_cfg.get("spacy_model", "en_core_web_sm")
        
        # Load spaCy NLP Engine
        try:
            self.nlp = spacy.load(self.spacy_model_name)
        except Exception:
            self.nlp = spacy.load("en_core_web_sm")

        # Load Presidio Analyzer
        self.presidio_analyzer = None
        if self.pipeline_cfg.get("enable_presidio", True) and HAS_PRESIDIO:
            try:
                self.presidio_analyzer = AnalyzerEngine()
            except Exception as e:
                logger.warning(f"Presidio Analyzer fallback: {e}")

    def _detect_regex(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII entities using regular expressions."""
        matches = []
        if not self.pipeline_cfg.get("enable_regex", True):
            return matches

        for pii_type, pattern in self.regex_patterns.items():
            if pii_type == "CREDIT_CARD":
                for match in re.finditer(pattern, text):
                    raw_val = match.group(0)
                    digits = re.sub(r'\D', '', raw_val)
                    if 13 <= len(digits) <= 16 and not raw_val.startswith("0"):
                        matches.append({
                            "start": match.start(),
                            "end": match.end(),
                            "text": raw_val,
                            "entity_type": pii_type,
                            "confidence": 0.95,
                            "source": "regex"
                        })
            elif pii_type == "PHONE":
                for match in re.finditer(pattern, text):
                    raw_val = match.group(0)
                    digits = re.sub(r'\D', '', raw_val)
                    if len(digits) >= 10 and not raw_val.startswith("19") and not raw_val.startswith("20"):
                        matches.append({
                            "start": match.start(),
                            "end": match.end(),
                            "text": raw_val,
                            "entity_type": pii_type,
                            "confidence": 0.92,
                            "source": "regex"
                        })
            elif pii_type == "BANK_ACCOUNT":
                for match in re.finditer(pattern, text):
                    raw_val = match.group(0)
                    window = text[max(0, match.start()-30):match.end()+30].lower()
                    if len(raw_val) >= 9 and ("account" in window or "bank" in window):
                        matches.append({
                            "start": match.start(),
                            "end": match.end(),
                            "text": raw_val,
                            "entity_type": pii_type,
                            "confidence": 0.93,
                            "source": "regex"
                        })
            else:
                for match in re.finditer(pattern, text):
                    matches.append({
                        "start": match.start(),
                        "end": match.end(),
                        "text": match.group(0),
                        "entity_type": pii_type,
                        "confidence": 0.90,
                        "source": "regex"
                    })

        return matches

    def _detect_ner(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII entities using spaCy NER."""
        matches = []
        doc = self.nlp(text)
        
        mapping_labels = {
            "PERSON": "PERSON",
            "ORG": "ORGANIZATION",
            "GPE": "LOCATION",
            "LOC": "LOCATION",
            "DATE": "DATE_OF_BIRTH"
        }

        for ent in doc.ents:
            if ent.label_ in mapping_labels:
                entity_text = ent.text.strip()
                ent_type = mapping_labels[ent.label_]
                
                if len(entity_text) <= 2 or entity_text.upper() in self.BOILERPLATE_EXCLUSIONS:
                    continue
                
                if any(ex in entity_text.upper() for ex in ["PROSPECTUS", "COMPANIES ACT", "SEBI", "BID/OFFER"]):
                    continue

                if entity_text.upper() in self.KNOWN_LOCATIONS:
                    ent_type = "LOCATION"

                matches.append({
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "text": entity_text,
                    "entity_type": ent_type,
                    "confidence": 0.80,
                    "source": "spacy_ner"
                })

        return matches

    def _detect_presidio(self, text: str) -> List[Dict[str, Any]]:
        """Detect PII entities using Presidio Analyzer Engine."""
        matches = []
        if not self.presidio_analyzer:
            return matches

        try:
            results = self.presidio_analyzer.analyze(text=text, language="en")
            presidio_mapping = {
                "PERSON": "PERSON",
                "ORGANIZATION": "ORGANIZATION",
                "EMAIL_ADDRESS": "EMAIL",
                "PHONE_NUMBER": "PHONE",
                "LOCATION": "LOCATION",
                "CREDIT_CARD": "CREDIT_CARD",
                "US_SSN": "SSN",
                "IP_ADDRESS": "IP_ADDRESS",
                "DATE_TIME": "DATE_OF_BIRTH"
            }

            for res in results:
                if res.entity_type in presidio_mapping:
                    ent_text = text[res.start:res.end].strip()
                    if len(ent_text) <= 2 or ent_text.upper() in self.BOILERPLATE_EXCLUSIONS:
                        continue
                    
                    ent_type = presidio_mapping[res.entity_type]
                    if ent_text.upper() in self.KNOWN_LOCATIONS:
                        ent_type = "LOCATION"

                    matches.append({
                        "start": res.start,
                        "end": res.end,
                        "text": ent_text,
                        "entity_type": ent_type,
                        "confidence": float(res.score),
                        "source": "presidio"
                    })
        except Exception:
            pass

        return matches

    def detect(self, text: str) -> List[Dict[str, Any]]:
        """
        Runs hybrid PII detection combining Regex, spaCy NER, and Presidio,
        and returns non-overlapping detected PII entities.
        """
        if not text or not text.strip():
            return []

        all_matches = []
        all_matches.extend(self._detect_regex(text))
        all_matches.extend(self._detect_presidio(text))
        all_matches.extend(self._detect_ner(text))

        return resolve_overlaps(all_matches)
