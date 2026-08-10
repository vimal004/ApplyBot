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

        work_exp_summary = "\n".join([
            f"- {w['role']} at {w['company']} ({w['dates']}): {w['description']}"
            for w in getattr(config.profile, "work_experience", [])
        ])

        system_prompt = (
            "You are an expert AI Job Application Assistant acting on behalf of Vimal Manoharan, a Computer Science "
            "Engineering graduate from SRM Institute of Science and Technology (graduated May 2026, CGPA 8.91/10.0).\n\n"
            "CANDIDATE PROFILE:\n"
            f"- Full Name: {config.profile.full_name}, Email: {config.profile.email}, Phone: {config.profile.phone} (raw: {config.profile.raw_phone})\n"
            f"- Location: {config.profile.location}, University: {config.profile.university}\n"
            f"- Degree: Bachelor of Technology in Computer Science Engineering (B.Tech)\n"
            f"- Highest Qualification: B.Tech\n"
            f"- CGPA: {config.profile.gpa}, Graduation Year: {config.profile.graduation_year} (2026 Batch)\n"
            f"- Last Stipend Paid: {getattr(config.profile, 'last_stipend', '20,000 / month')}\n"
            f"- LinkedIn: {config.profile.linkedin_url}, GitHub: {config.profile.github_url}\n"
            f"- Resume Link: {config.profile.resume_gdrive_url}\n\n"
            f"VIMAL'S REAL PAID WORK EXPERIENCE & INTERNSHIPS:\n{work_exp_summary}\n\n"
            f"VIMAL'S GITHUB PROJECTS:\n{projects_summary}\n\n"
            "CRITICAL RULES FOR FORM ANSWERS:\n"
            "1. INTERNSHIP & PRIOR EXPERIENCE QUESTIONS:\n"
            "   - Vimal HAS paid internship & freelance work experience! Mention his roles at Aakar Labs (React Native Developer Intern on Aaku AI travel companion) and KSK Electronics (Software Developer Intern on ERP & RAG SOP).\n"
            "   - DO NOT say 'No prior experience' or 'only personal projects'!\n"
            "   - For 'Company where most impact work done', specify 'Siddha Shivalayas Clinic (https://siddhashivalayas.vercel.app)' or 'Aakar Labs'.\n"
            "   - For 'Link to product worked on', give 'https://siddhashivalayas.vercel.app'.\n"
            "   - For 'last Stipend Paid', answer '20,000 / month'.\n\n"
            "2. QUALIFICATION & GRADUATION YEAR:\n"
            "   - Highest Qualification: select/fill 'B.Tech'.\n"
            "   - Graduation year: select '2026'.\n"
            "   - DO NOT fill any 'Other:' text input if a standard option (like 2026 or B.Tech) is chosen. Leave 'Other:' text input empty!\n\n"
            "3. DOMAIN-CURATED ESSAY QUESTIONS (e.g. 'What excites you about the role?'):\n"
            "   - Carefully analyze target company and role domain (e.g. Product Management, FinTech, AI, Full-Stack).\n"
            "   - Tailor answer SPECIFICALLY to that domain and company! (e.g. for Product Intern at NxtPe FinTech: focus on product analytics, payments UX, feature roadmap, and reference product-centric work like Aaku AI travel app or QuensultingAI Voice Receptionist).\n"
            "   - DO NOT mention irrelevant random projects!\n\n"
            "4. ACTION SCHEME:\n"
            "   - For text input fields: use action='fill', set 'index'.\n"
            "   - For radio/checkbox/dropdown choice questions: use action='click_option', set 'question_index'. The 'value' MUST be an EXACT option string listed.\n"
            "   - Generate actions for ALL text fields and choice questions.\n\n"
            "Output ONLY a valid JSON array of objects."
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
            print(f"[LLM Action Plan Error] {e}. Using Local Deterministic Heuristic Plan Generator...")
            
        fallback_plan = []
        for f in fields:
            idx = f.get("index")
            lbl = f.get("label", "").lower()
            val = ""
            if "email" in lbl: val = config.profile.email
            elif "location" in lbl or "city" in lbl or "address" in lbl: val = config.profile.location
            elif "first name" in lbl: val = config.profile.first_name
            elif "last name" in lbl: val = config.profile.last_name
            elif "phone" in lbl or "mobile" in lbl or "contact" in lbl: val = config.profile.raw_phone
            elif "linkedin" in lbl: val = config.profile.linkedin_url
            elif "github" in lbl or "portfolio" in lbl or "website" in lbl: val = config.profile.github_url
            elif "college" in lbl or "university" in lbl or "institute" in lbl: val = config.profile.university
            elif "degree" in lbl or "branch" in lbl or "major" in lbl: val = config.profile.degree
            elif "gpa" in lbl or "cgpa" in lbl or "marks" in lbl: val = config.profile.gpa
            elif "stipend" in lbl or "salary" in lbl: val = getattr(config.profile, "last_stipend", "20,000 / month")
            elif "impact" in lbl or "company" in lbl: val = "Siddha Shivalayas Clinic (https://siddhashivalayas.vercel.app)"
            elif "product" in lbl or "link" in lbl or "app store" in lbl or "weblink" in lbl: val = "https://siddhashivalayas.vercel.app"
            elif "prior" in lbl or "internship" in lbl or "experience" in lbl: val = "React Native Frontend Developer Intern at Aakar Labs (7 months, Aaku AI travel companion) and Software Developer Intern at KSK Electronics (3 months, full-stack ERP & RAG SOP)."
            elif "excite" in lbl or "why" in lbl or "motivation" in lbl: val = f"I'm excited about the {role} role at {company} because it offers the opportunity to work on high-impact products and user experiences. My background developing production-grade applications like Aaku AI travel companion app and QuensultingAI Voice Receptionist has given me strong domain skills in product development and analytics."
            elif "video" in lbl or "youtube" in lbl or "2 minute" in lbl: val = "Video link will be provided upon request"
            elif "name" in lbl and "file" not in lbl: val = config.profile.full_name
            
            if val and idx is not None:
                fallback_plan.append({"index": idx, "action": "fill", "label": f.get("label", ""), "value": val})

        for rq in radio_questions:
            q_idx = rq.get("question_index")
            q_title = rq.get("question", "").lower()
            opts = rq.get("options", [])
            chosen_opt = ""
            if "graduat" in q_title or "batch" in q_title or "year" in q_title:
                for o in opts:
                    if "2026" in o: chosen_opt = o; break
            elif "qualification" in q_title or "degree" in q_title or "highest" in q_title:
                for o in opts:
                    if "b.tech" in o.lower() or "btech" in o.lower() or "b.e" in o.lower(): chosen_opt = o; break
            elif "available" in q_title or "start" in q_title or "notice" in q_title:
                for o in opts:
                    if "15" in o or "immediate" in o.lower() or "less than" in o.lower(): chosen_opt = o; break
            if not chosen_opt and opts:
                for o in opts:
                    if "other" not in o.lower(): chosen_opt = o; break
                if not chosen_opt: chosen_opt = opts[0]
            if chosen_opt and q_idx is not None:
                fallback_plan.append({"question_index": q_idx, "action": "click_option", "label": rq.get("question", ""), "value": chosen_opt})

        return fallback_plan
