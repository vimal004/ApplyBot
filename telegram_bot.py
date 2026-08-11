import os
import re
from typing import Dict, Any
from config import config
from parser import TelegramJobParser
from tailorer import ResumeTailorer
from compiler import LaTeXCompiler
from email_sender import HREmailSender
from form_filler import JobFormAutoFiller

class ApplyBotPipeline:
    """
    Master ApplyBot Pipeline.
    Orchestrates Telegram Post Ingestion -> Eligibility Check -> ATS Resume Tailoring ->
    PDF Resume Compilation -> HR Emailing / Form Auto-Filling.
    """

    @staticmethod
    def process_referral(raw_telegram_text: str, superfast_mode: bool = False, job_dict: Dict[str, Any] = None) -> Dict[str, Any]:
        base_tex = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.tex")
        
        # 1. Parse Telegram Post if job_dict is not supplied
        if job_dict:
            job = job_dict
        else:
            parsed_res = TelegramJobParser.parse_message(raw_telegram_text)
            if isinstance(parsed_res, list) and len(parsed_res) > 0:
                job = parsed_res[0]
            elif isinstance(parsed_res, dict):
                job = parsed_res
            else:
                job = {
                    "company": "Company", "role": "Software Engineer", "batch": "Any",
                    "salary": "Not Specified", "location": "India", "requirements": [],
                    "raw_text": raw_telegram_text, "apply_target": "", "apply_mode": "UNKNOWN"
                }

        company_clean = re.sub(r'[^a-zA-Z0-9]', '_', job.get("company", "Company"))[:25].strip('_')
        role_clean = re.sub(r'[^a-zA-Z0-9]', '_', job.get("role", "Role"))[:25].strip('_')
        
        output_tex = os.path.join(config.output_dir, f"Resume_{company_clean}_{role_clean}.tex")
        output_pdf = os.path.join(config.output_dir, f"Vimal_Manoharan_Resume_{company_clean}.pdf")
        
        # 2. Tailor LaTeX Resume
        ResumeTailorer.tailor_latex_resume(base_tex, job, output_tex)
        
        # Read the tailored LaTeX code to compute the exact final ATS score
        with open(output_tex, 'r', encoding='utf-8') as f:
            tailored_content = f.read()
        ats_score, found_kw, missing_kw = ResumeTailorer.calculate_ats_score(job, tailored_content)
        
        # 3. Compile LaTeX to PDF Resume
        success_compile, compile_msg = LaTeXCompiler.compile_tex_to_pdf(output_tex, output_pdf)
        
        # 4. Prepare Application Action (Email vs Form Auto-fill)
        action_result = {}
        if job["apply_mode"] == "EMAIL":
            email_payload = HREmailSender.generate_email_payload(job, output_pdf)
            sent, status_msg = HREmailSender.send_email(email_payload) if superfast_mode else (True, "Email draft ready for your review!")
            action_result = {
                "type": "EMAIL",
                "payload": email_payload,
                "sent": sent,
                "status": status_msg
            }
        else:
            form_payload = JobFormAutoFiller.prepare_form_payload(job, output_pdf)
            executed, status_msg, execution_details = JobFormAutoFiller.execute_auto_fill(form_payload, superfast_mode)
            action_result = {
                "type": "FORM_AUTOFILL",
                "payload": form_payload,
                "status": status_msg
            }

        return {
            "job": job,
            "ats_score": ats_score,
            "found_keywords": found_kw,
            "missing_keywords": missing_kw,
            "pdf_path": output_pdf,
            "action_result": action_result
        }
