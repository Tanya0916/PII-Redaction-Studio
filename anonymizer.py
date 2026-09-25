import re
import random
import logging
from typing import Dict, List, Any
from faker import Faker

logger = logging.getLogger("PIIRedactor")


class PIIAnonymizer:
    """
    Handles realistic fake data generation using Faker, maintaining strict consistency
    across the entire document so that identical original values always map to the same fake value.
    """

    def __init__(self, locale: str = "en_IN", seed: int = 42):
        # Set seed for reproducible fake data generation if desired
        Faker.seed(seed)
        random.seed(seed)
        self.fake = Faker([locale, "en_US"])
        
        # Primary mapping: original_text -> replacement_text
        self.mapping: Dict[str, str] = {}
        
        # Metadata mapping: original_text -> dict info
        self.mapping_details: Dict[str, Dict[str, Any]] = {}

    def _generate_fake(self, original_text: str, entity_type: str) -> str:
        """Generates a realistic fake value tailored to the PII entity type."""
        entity_type = entity_type.upper()

        if entity_type == "PERSON":
            fake_val = self.fake.name()
        elif entity_type == "ORGANIZATION":
            fake_val = self.fake.company() + " Pvt. Ltd."
        elif entity_type == "EMAIL":
            # Generate email matching fake company or fake name
            name_part = self.fake.first_name().lower()
            fake_val = f"{name_part}@{self.fake.domain_name()}"
        elif entity_type == "PHONE":
            if "+91" in original_text:
                fake_val = f"+91 {random.randint(7000000000, 9999999999)}"
            else:
                fake_val = self.fake.phone_number()
        elif entity_type == "DATE_OF_BIRTH":
            # Match date format if possible
            if "/" in original_text:
                fake_val = self.fake.date(pattern="%d/%m/%Y")
            elif "-" in original_text:
                fake_val = self.fake.date(pattern="%d-%m-%Y")
            else:
                fake_val = self.fake.date(pattern="%B %d, %Y")
        elif entity_type == "LOCATION":
            fake_val = self.fake.city()
        elif entity_type == "CREDIT_CARD":
            fake_val = self.fake.credit_card_number()
        elif entity_type == "SSN":
            fake_val = self.fake.ssn()
        elif entity_type == "PAN":
            # Formatted Indian Permanent Account Number: 5 letters, 4 digits, 1 letter
            letters1 = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=5))
            digits = "".join(random.choices("0123456789", k=4))
            letter2 = random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            fake_val = f"{letters1}{digits}{letter2}"
        elif entity_type == "AADHAAR":
            part1 = random.randint(2000, 9999)
            part2 = random.randint(1000, 9999)
            part3 = random.randint(1000, 9999)
            fake_val = f"{part1} {part2} {part3}"
        elif entity_type == "BANK_ACCOUNT":
            fake_val = str(random.randint(100000000000, 999999999999))
        elif entity_type == "IP_ADDRESS":
            fake_val = self.fake.ipv4()
        else:
            fake_val = f"[REDACTED_{entity_type}]"

        return fake_val

    def get_replacement(self, original_text: str, entity_type: str) -> str:
        """
        Returns consistent fake value for original text. If already mapped,
        returns the existing replacement to guarantee cross-document consistency.
        """
        clean_key = original_text.strip()
        
        if clean_key in self.mapping:
            self.mapping_details[clean_key]["occurrences"] += 1
            return self.mapping[clean_key]

        replacement = self._generate_fake(clean_key, entity_type)
        
        # Ensure we don't accidentally produce the same replacement for different originals
        existing_values = set(self.mapping.values())
        retry_count = 0
        while replacement in existing_values and retry_count < 10:
            replacement = self._generate_fake(clean_key, entity_type)
            retry_count += 1

        self.mapping[clean_key] = replacement
        self.mapping_details[clean_key] = {
            "replacement": replacement,
            "entity_type": entity_type,
            "occurrences": 1
        }
        return replacement

    def anonymize_text(self, text: str, matches: List[Dict[str, Any]]) -> str:
        """
        Replaces detected PII entities in a text string with consistent fake values.
        Replaces from right to left (descending order of start index) to maintain character offsets.
        """
        if not text or not matches:
            return text

        # Sort matches in reverse start index order
        sorted_matches = sorted(matches, key=lambda x: x["start"], reverse=True)
        anonymized_text = text

        for match in sorted_matches:
            start, end = match["start"], match["end"]
            orig_val = match["text"]
            ent_type = match["entity_type"]

            fake_val = self.get_replacement(orig_val, ent_type)
            anonymized_text = anonymized_text[:start] + fake_val + anonymized_text[end:]

        return anonymized_text

    def get_mapping_dict(self) -> Dict[str, str]:
        """Returns the simple mapping dictionary (original -> fake)."""
        return self.mapping

    def get_detailed_mapping(self) -> Dict[str, Dict[str, Any]]:
        """Returns detailed mapping dictionary containing entity types and count."""
        return self.mapping_details
