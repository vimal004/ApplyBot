import re
import json
import urllib.request
from typing import Dict, Any, List
from config import config

class TelegramJobParser:
    """
    Smart LLM-Powered Telegram Referral Message Parser.
    Uses Groq LLM (llama-3.1-8b-instant) to parse ANY arbitrarily structured Telegram post
    into a clean JSON structure, with a robust heuristic fallback.
    """

    LLM_SYSTEM_PROMPT = """
You are an expert recruitment parser. Extract structured job details from the provided Telegram job referral message.
Return ONLY valid JSON matching this exact structure:
{
  "company": "Company Name",
  "role": "Job Role / Designation",
  "batch": "Eligible Batches (e.g. 2024/2025 or 2020 and before)",
  "salary": "Salary / CTC / Stipend details (e.g. 20-35 LPA or ₹30,000/month)",
  "location": "Job Location",
  "requirements": ["Requirement 1", "Requirement 2", "Requirement 3"],
  "apply_target": "Email address OR application URL",
  "apply_mode": "EMAIL" or "LINK",
  "subject_line": "Target email subject line if mentioned in post (else empty string)"
}
Do not include markdown backticks or any conversational text outside the JSON object.
"""

    @staticmethod
    def parse_message(raw_text: str) -> Dict[str, Any]:
        text = raw_text.strip()

        # 1. Try Groq LLM Parsing if API key is present
        if config.groq.api_key:
            llm_result = TelegramJobParser._parse_with_groq(text)
            if llm_result:
                # Add candidate eligibility evaluation
                llm_result["is_eligible"] = TelegramJobParser._check_batch_eligibility(
                    llm_result.get("batch", ""), candidate_batch="2026"
                )
                llm_result["raw_text"] = raw_text
                return llm_result

        # 2. Fallback Heuristic Parser if LLM is unavailable or unfulfilled
        return TelegramJobParser._parse_with_heuristics(text)

    @staticmethod
    def _parse_with_groq(text: str) -> Dict[str, Any]:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.groq.api_key}",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        }
        
        payload = {
            "model": config.groq.model_name,
            "messages": [
                {"role": "system", "content": TelegramJobParser.LLM_SYSTEM_PROMPT.strip()},
                {"role": "user", "content": text}
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                content = res_data['choices'][0]['message']['content'].strip()
                parsed_json = json.loads(content)
                
                # Sanitize extracted target
                apply_target = parsed_json.get("apply_target", "")
                apply_mode = parsed_json.get("apply_mode", "UNKNOWN").upper()
                
                if "@" in apply_target and not apply_target.startswith("http"):
                    apply_mode = "EMAIL"
                elif apply_target.startswith("http"):
                    apply_mode = "LINK"
                    
                return {
                    "company": parsed_json.get("company", "Company")[:30],
                    "role": parsed_json.get("role", "Software Engineer")[:30],
                    "batch": parsed_json.get("batch", "Any"),
                    "salary": parsed_json.get("salary", "Not Specified"),
                    "location": parsed_json.get("location", "India"),
                    "requirements": parsed_json.get("requirements", []),
                    "apply_target": apply_target,
                    "apply_mode": apply_mode,
                    "subject_line": parsed_json.get("subject_line", "")
                }
        except Exception as e:
            print(f"[Groq Parser Note] Falling back to heuristics ({e})")
            return None

    @staticmethod
    def _parse_with_heuristics(text: str) -> Dict[str, Any]:
        field_boundary = r'(?=(?:Company|Role|Batch|Stipend|Salary|CTC|Location|Internship|Job Description|Key Responsibilities|Requirements|Eligibility|Who should apply|What you|How to Apply|Email|Subject|\n|\r|\Z))'

        # Company
        comp_m = re.search(r'Company\s*[:\-]\s*(.+?)' + field_boundary, text, re.IGNORECASE)
        company = comp_m.group(1).strip() if comp_m else "Company"
        company = re.sub(r'[^a-zA-Z0-9\s]', '', company)[:30].strip() or "Company"

        # Role
        role_m = re.search(r'Role\s*[:\-]\s*(.+?)' + field_boundary, text, re.IGNORECASE)
        role = role_m.group(1).strip() if role_m else "Software Engineer"
        role = re.sub(r'[^a-zA-Z0-9\s/]', '', role)[:30].strip() or "Role"

        # Batch
        batch_m = re.search(r'Batch\s*[:\-]\s*(.+?)' + field_boundary, text, re.IGNORECASE)
        batch = batch_m.group(1).strip() if batch_m else "Any"

        # Salary / CTC
        sal_m = re.search(r'(?:Salary|Stipend|CTC)\s*[:\-]\s*(.+?)' + field_boundary, text, re.IGNORECASE)
        salary = sal_m.group(1).strip() if sal_m else "Not Specified"

        # Location
        loc_m = re.search(r'Location\s*[:\-]\s*(.+?)' + field_boundary, text, re.IGNORECASE)
        location = loc_m.group(1).strip() if loc_m else "Remote / India"

        # Requirements
        requirements = []
        req_match = re.search(r'(?:Requirements|Job Description|Key Responsibilities|Eligibility|Who should apply|What you)\s*[:\-]?\s*([\s\S]+?)(?=How to Apply|\Z)', text, re.IGNORECASE)
        if req_match:
            raw_reqs = req_match.group(1)
            for item in re.split(r'[*•\-]\s*', raw_reqs):
                cleaned = item.strip()
                if cleaned and len(cleaned) > 5:
                    requirements.append(cleaned[:120])

        # Target (Email vs URL)
        apply_target = ""
        apply_mode = "UNKNOWN"
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        url_match = re.search(r'https?://[^\s]+', text)

        if email_match:
            apply_target = re.sub(r'(\.(?:ai|com|in|org|net|io|co|edu))[a-zA-Z]+$', r'\1', email_match.group(0), flags=re.IGNORECASE)
            apply_mode = "EMAIL"
        elif url_match:
            apply_target = url_match.group(0)
            apply_mode = "LINK"

        is_eligible = TelegramJobParser._check_batch_eligibility(batch, candidate_batch="2026")

        return {
            "company": company,
            "role": role,
            "batch": batch,
            "salary": salary,
            "location": location,
            "requirements": requirements,
            "raw_text": text,
            "apply_target": apply_target,
            "apply_mode": apply_mode,
            "subject_line": "",
            "is_eligible": is_eligible
        }

    @staticmethod
    def _check_batch_eligibility(batch_str: str, candidate_batch: str = "2026") -> bool:
        if not batch_str or batch_str.lower() in ["any", "all"]:
            return True
            
        if candidate_batch in batch_str:
            return True
            
        before_match = re.search(r'(\d{4})\s*and\s*before', batch_str, re.IGNORECASE)
        if before_match:
            cutoff = int(before_match.group(1))
            if int(candidate_batch) > cutoff:
                return False
                
        return True
