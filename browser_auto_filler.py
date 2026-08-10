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
            "location": config.profile.location,
            "college": config.profile.university,
            "degree": config.profile.degree,
            "gpa": config.profile.gpa,
            "grad_year": str(config.profile.graduation_year),
            "linkedin": config.profile.linkedin_url,
            "github": config.profile.github_url,
            "portfolio": config.profile.portfolio_url,
            "resume_gdrive_url": config.profile.resume_gdrive_url
        }

        # Step 3: Launch interactive Playwright browser window
        plan_json_str = json.dumps(action_plan)
        profile_json_str = json.dumps(profile_dict)
        job_json_str = json.dumps(job_data or {})
        subprocess.Popen([python_bin, runner_file, form_url, plan_json_str, pdf_path, profile_json_str, job_json_str])

        return True, f"Launched Playwright browser with pre-filled form fields for {form_url}. Review the opened window and click Submit!", {
            "dom_info": dom_info,
            "action_plan": action_plan
        }

    @staticmethod
    def _generate_llm_action_plan(dom_info: Dict[str, Any], job_data: Dict[str, Any], pdf_path: str) -> list:
        fields = dom_info.get("fields", [])
        radio_questions = dom_info.get("radio_questions", [])
        if not fields and not radio_questions:
            return []

        company = job_data.get("company", "Company")
        role = job_data.get("role", "Role")
        raw_text = job_data.get("raw_text", "")

        projects_summary = "\n".join([
            f"- {p['name']} ({p['tech']}): {p['description']} [Repo: {p['url']}]"
            for p in config.profile.key_projects
        ])

        system_prompt = (
            "You are an expert AI Job Application Assistant acting on behalf of Vimal Manoharan, a Computer Science "
            "Engineering student at SRM Institute of Science and Technology (graduating 2026, CGPA 8.91/10.0).\n"
            "Candidate Profile:\n"
            f"- Full Name: {config.profile.full_name}, Email: {config.profile.email}, Phone: {config.profile.phone}\n"
            f"- Location: {config.profile.location}, University: {config.profile.university}\n"
            f"- Degree: {config.profile.degree}, CGPA: {config.profile.gpa}\n"
            f"- Graduation Year: {config.profile.graduation_year}\n"
            f"- LinkedIn: {config.profile.linkedin_url}, GitHub: {config.profile.github_url}\n"
            f"- Resume Link: {config.profile.resume_gdrive_url}\n\n"
            f"VIMAL'S GITHUB PROJECTS:\n{projects_summary}\n\n"
            "CRITICAL RULES FOR FORM FILLING:\n"
            "1. TEXT INPUT FIELDS: Use action='fill'. Set 'index' to the field's index number.\n"
            "   - Standard fields: use exact profile values.\n"
            "   - Essay/Custom questions: Write 2-4 impressive sentences referencing relevant projects.\n"
            "2. RADIO / CHOICE QUESTIONS: Use action='click_option'. Set 'question_index' to the question's index number.\n"
            "   - The 'value' MUST be one of the EXACT option strings listed for that question.\n"
            "   - Graduation year is 2026. Available to start within 15 days.\n"
            "   - Do NOT select 'Other:' unless no listed option matches.\n"
            "3. Generate an action for EVERY text field AND EVERY radio question.\n\n"
            "Output ONLY a valid JSON array of objects:\n"
            "[\n"
            '  {"index": 0, "action": "fill", "label": "question text", "value": "answer text"},\n'
            '  {"question_index": 1, "action": "click_option", "label": "question text", "value": "exact option text"}\n'
            "]"
        )

        user_prompt = (
            f"Applying for: {role} at {company}\n"
            f"Job Summary:\n{raw_text[:2000]}\n\n"
            f"=== TEXT INPUT FIELDS ===\n{json.dumps(fields, indent=2)}\n\n"
            f"=== RADIO/CHOICE QUESTIONS ===\n{json.dumps(radio_questions, indent=2)}\n\n"
            "Generate JSON array of actions for ALL text fields AND ALL radio questions."
        )

        try:
            llm_res = ResumeTailorer.ask_groq_llm(user_prompt, system_prompt, max_tokens=2000)
            if "```" in llm_res:
                parts = llm_res.split("```")
                for p in parts:
                    if "[" in p and "]" in p:
                        llm_res = p.replace("json", "").strip()
                        break
            plan = json.loads(llm_res.strip())
            return plan if isinstance(plan, list) else []
        except Exception as e:
            print(f"[LLM Action Plan Error] {e}")
            return []
