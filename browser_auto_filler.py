import os
import json
import subprocess
from typing import Dict, Any, Tuple
from config import config
from form_parser import PlaywrightFormParser
from tailorer import ResumeTailorer

class AutomatedBrowserFiller:
    """
    Automated Playwright Interactive Form Filler.
    1. Inspects live form URL using Playwright.
    2. Sends real form schema + candidate profile to Groq LLM to match fields and generate answers.
    3. Launches interactive browser window, populates all fields, and leaves window open for manual review & submit.
    """

    @staticmethod
    def process_and_fill_form(form_payload: Any, job_data: Dict[str, Any] = None, pdf_path: str = "") -> Tuple[bool, str, Dict[str, Any]]:
        python_bin = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
        runner_file = os.path.join(os.path.dirname(__file__), "browser_fill_runner.py")
        
        if isinstance(form_payload, str):
            form_url = form_payload
            profile_dict = {}
        else:
            form_url = form_payload.get("apply_url", "")
            profile_dict = form_payload.get("profile", {})
            pdf_path = pdf_path or profile_dict.get("resume_path", "")
        
        if not form_url:
            return False, "No valid form URL provided.", {}

        # Step 1: Inspect form DOM via Playwright
        print(f"[ApplyBot Auto-Filler] Inspecting live form DOM at {form_url}...")
        dom_info = PlaywrightFormParser.inspect_form_page(form_url, python_bin)
        
        if "error" in dom_info and not dom_info.get("fields"):
            print(f"[ApplyBot Auto-Filler] Could not inspect DOM ahead of time. Proceeding with standard profile filler.")
            dom_info = {"fields": [], "radio_questions": []}

        # Step 2: Use Groq LLM to generate an Action Plan for the REAL fields found
        action_plan = AutomatedBrowserFiller._generate_llm_action_plan(dom_info, job_data or {}, pdf_path)

        profile_dict = {
            "email": config.profile.email,
            "name": config.profile.full_name,
            "first_name": config.profile.first_name,
            "last_name": config.profile.last_name,
            "phone": config.profile.phone,
            "college": config.profile.university,
            "degree": config.profile.degree,
            "gpa": config.profile.gpa,
            "grad_year": str(config.profile.graduation_year),
            "linkedin": config.profile.linkedin_url,
            "github": config.profile.github_url,
            "resume_gdrive_url": config.profile.resume_gdrive_url
        }

        # Step 3: Launch interactive Playwright browser window
        plan_json_str = json.dumps(action_plan)
        profile_json_str = json.dumps(profile_dict)
        subprocess.Popen([python_bin, runner_file, form_url, plan_json_str, pdf_path, profile_json_str])

        return True, f"Launched Playwright browser with pre-filled form fields for {form_url}. Review the opened window and click Submit!", {
            "dom_info": dom_info,
            "action_plan": action_plan
        }

    @staticmethod
    def _generate_llm_action_plan(dom_info: Dict[str, Any], job_data: Dict[str, Any], pdf_path: str) -> list:
        if not dom_info.get("fields") and not dom_info.get("radio_questions"):
            return []

        company = job_data.get("company", "Company")
        role = job_data.get("role", "Role")

        system_prompt = (
            "You are an automated web form solver. You match candidate profile data to HTML form elements and answer "
            "form questions in a natural, genuine human tone.\n"
            "Candidate Profile:\n"
            f"- Name: {config.profile.full_name}\n"
            f"- Email: {config.profile.email}\n"
            f"- Phone: {config.profile.phone}\n"
            f"- University: {config.profile.university}\n"
            f"- CGPA: {config.profile.gpa}\n"
            f"- Graduation Year: {config.profile.graduation_year}\n"
            f"- LinkedIn: {config.profile.linkedin_url}\n"
            f"- GitHub: {config.profile.github_url}\n\n"
            "Output ONLY a JSON array of actions matching this schema:\n"
            "[\n"
            '  {"action": "fill", "label": "question label", "value": "value to type"},\n'
            '  {"action": "click_option", "label": "question label", "value": "exact option text to click"}\n'
            "]"
        )

        user_prompt = (
            f"Role: {role} at {company}\n"
            f"Form DOM Elements:\n{json.dumps(dom_info, indent=2)[:2000]}\n"
            "Generate the JSON array of actions."
        )

        try:
            llm_res = ResumeTailorer.ask_groq_llm(user_prompt, system_prompt)
            if "```" in llm_res:
                llm_res = llm_res.split("```")[1].replace("json", "").strip()
            return json.loads(llm_res)
        except Exception as e:
            print(f"[LLM Action Plan Error] {e}")
            return []
