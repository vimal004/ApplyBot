import re
import json
import urllib.request
from typing import Dict, Any, List, Optional
from config import config

from llm_manager import llm_manager, TaskType

class TelegramJobParser:
    """
    Smart LLM-Powered Telegram Referral Message Parser.
    Uses LLMManager with multi-provider fallback (Groq -> Cerebras -> Gemini -> OpenRouter)
    to parse arbitrarily structured Telegram posts into JSON, with heuristic fallback.
    """

    LLM_SYSTEM_PROMPT = """You are an expert recruitment parser. Extract job details from Telegram posts.
Return ONLY valid JSON matching this structure:
{
  "jobs": [
    {
      "company": "Company Name",
      "role": "Job Role / Designation",
      "batch": "Eligible Batches (e.g. 2024/2025/2026)",
      "salary": "Salary / CTC / Stipend details",
      "location": "Job Location",
      "requirements": ["Req 1", "Req 2"],
      "apply_target": "Email address OR application URL",
      "apply_mode": "EMAIL" or "LINK",
      "subject_line": "Target email subject line if mentioned"
    }
  ]
}"""

    @staticmethod
    def parse_message(raw_text: str) -> List[Dict[str, Any]]:
        text = raw_text.strip()

        # 1. Try LLM Parsing across task routes
        llm_result = TelegramJobParser._parse_with_llm(text)
        if llm_result:
            for job in llm_result:
                job["is_eligible"] = TelegramJobParser._check_batch_eligibility(
                    job.get("batch", ""), candidate_batches=("2025", "2026")
                )
                job["raw_text"] = raw_text
            return llm_result

        # 2. Fallback Heuristic Parser if all LLM routes are unfulfilled
        fallback_job = TelegramJobParser._parse_with_heuristics(text)
        return [fallback_job]

    @staticmethod
    def _parse_with_llm(text: str) -> Optional[List[Dict[str, Any]]]:
        try:
            content = llm_manager.generate(
                task=TaskType.PARSING,
                prompt=text,
                system_prompt=TelegramJobParser.LLM_SYSTEM_PROMPT.strip(),
                max_tokens=1000,
                temperature=0.1,
                json_mode=True
            )
            if not content:
                return None

            # Robust JSON extraction
            start_idx = content.find("{")
            end_idx = content.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                content = content[start_idx:end_idx+1]

            parsed_json = json.loads(content)
            
            raw_jobs = parsed_json.get("jobs", [])
            if not isinstance(raw_jobs, list):
                if isinstance(parsed_json, dict) and "company" in parsed_json:
                    raw_jobs = [parsed_json]
                else:
                    raw_jobs = []

            processed_jobs = []
            for job in raw_jobs:
                apply_target = str(job.get("apply_target") or "")
                apply_mode = str(job.get("apply_mode") or "UNKNOWN").upper()
                
                if "@" in apply_target and not apply_target.startswith("http"):
                    apply_mode = "EMAIL"
                elif apply_target.startswith("http"):
                    apply_mode = "LINK"
                    
                processed_jobs.append({
                    "company": job.get("company", "Company")[:30],
                    "role": job.get("role", "Software Engineer")[:30],
                    "batch": job.get("batch", "Any"),
                    "salary": job.get("salary", "Not Specified"),
                    "location": job.get("location", "India"),
                    "requirements": job.get("requirements", []),
                    "apply_target": apply_target,
                    "apply_mode": apply_mode,
                    "subject_line": job.get("subject_line", "")
                })
            return processed_jobs if processed_jobs else None
        except Exception as e:
            print(f"[LLM Parser Note] Falling back to heuristics ({e})")
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

        is_eligible = TelegramJobParser._check_batch_eligibility(batch, candidate_batches=("2025", "2026"))

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
    def _check_batch_eligibility(batch_str: str, candidate_batches: tuple = ("2025", "2026")) -> bool:
        if not batch_str:
            return True
            
        batch_lower = batch_str.lower().strip()
        if batch_lower in ["any", "all", "not specified", "n/a", "any batch", "fresher", "freshers"]:
            return True

        # Check for year ranges like 2023-2026 or 2024-2025
        range_match = re.search(r'\b(20\d\d)\s*[\-\u2013\u2014to]+\s*(20\d\d)\b', batch_str)
        if range_match:
            start_yr = int(range_match.group(1))
            end_yr = int(range_match.group(2))
            years_in_range = [str(y) for y in range(start_yr, end_yr + 1)]
            if any(b in years_in_range for b in candidate_batches):
                return True
            return False

        # Extract all explicit 4-digit years (e.g. 2023, 2024, 2025, 2026, 2027)
        found_years = re.findall(r'\b(20\d\d)\b', batch_str)
        if found_years:
            # If any target candidate batch (2025 or 2026) is in the explicitly listed years -> eligible
            if any(cb in found_years for cb in candidate_batches):
                return True
            # Check "before" phrase e.g. "2025 and before" vs "2024 and before"
            before_match = re.search(r'\b(20\d\d)\s*(?:and|&)?\s*before\b', batch_str, re.IGNORECASE)
            if before_match:
                cutoff = int(before_match.group(1))
                if any(int(cb) <= cutoff for cb in candidate_batches):
                    return True
                return False
            # Explicit 4-digit years were found, but NONE matched candidate batches 2025 or 2026
            return False

        return True
