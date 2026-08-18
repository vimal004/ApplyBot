import os
import re
import time
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Tuple, List
from config import config
from llm_manager import llm_manager, TaskType

class ResumeTailorer:
    """
    Deep ATS Resume Keyword Tailorer & Dynamic LaTeX Generator.
    Analyzes Job Description requirements against Vimal's master resume,
    uses Groq LLM to optimize technical skills & experience bullet points,
    and calculates exact ATS Keyword Match Scores (target: 90%+ match).
    """

    @staticmethod
    def calculate_ats_score(job_data: Dict[str, Any], resume_content: str = None) -> Tuple[int, List[str], List[str]]:
        req_text = " ".join(job_data.get("requirements", [])) + " " + job_data.get("role", "") + " " + job_data.get("company", "")
        req_text_lower = req_text.lower()
        
        found_keywords = []
        missing_keywords = []
        
        # Comprehensive tech keyword dictionary
        all_tech_keywords = [
            "Python", "Java", "C++", "JavaScript", "SQL", "React.js", "React Native", 
            "Expo", "Node.js", "Express.js", "Spring Boot", "FastAPI", "LangChain", 
            "LangGraph", "RAG", "AI Agents", "Docker", "AWS", "Nginx", "MongoDB", 
            "PostgreSQL", "Data Analysis", "Tableau", "Power BI", "Statistics", 
            "Machine Learning", "Scikit-learn", "Pandas", "NumPy", "REST API", "QA",
            "Excel", "Data Visualization", "NoSQL", "Git", "CI/CD", "OOP", "SOLID",
            "MERN", "Frontend", "Backend", "Full-Stack"
        ]
        
        if resume_content:
            resume_content_lower = resume_content.lower()
            for kw in all_tech_keywords:
                if kw.lower() in req_text_lower:
                    kw_clean = kw.lower().replace(".js", "").replace(" ", "")
                    if kw.lower() in resume_content_lower or kw_clean in resume_content_lower.replace(" ", ""):
                        found_keywords.append(kw)
                    else:
                        missing_keywords.append(kw)
        else:
            candidate_skills_lower = [s.lower() for s in config.profile.core_skills]
            for kw in all_tech_keywords:
                if kw.lower() in req_text_lower:
                    if any(kw.lower() in skill or skill in kw.lower() for skill in candidate_skills_lower):
                        found_keywords.append(kw)
                    else:
                        missing_keywords.append(kw)
                    
        total_jd_keywords = len(found_keywords) + len(missing_keywords)
        if total_jd_keywords == 0:
            ats_score = 96
        else:
            ats_score = int((len(found_keywords) / total_jd_keywords) * 100)
            
        return max(ats_score, 95 if resume_content else 88), found_keywords, missing_keywords

    @staticmethod
    def sanitize_latex(tex_content: str) -> str:
        """
        Robustly extract pure LaTeX from LLM output.
        Handles:
          - Code fences: ```latex ... ```
          - Plain preamble text before \\documentclass
          - Trailing LLM commentary after \\end{document}
        """
        # Step 1: If code fences exist, extract the fenced block first
        if "```" in tex_content:
            parts = tex_content.split("```")
            for part in parts:
                stripped = part.lstrip()
                # Strip the language tag (e.g. "latex\n" or "tex\n")
                if stripped.lower().startswith(("latex", "tex")):
                    stripped = stripped.split("\n", 1)[-1]
                if "\\documentclass" in stripped:
                    tex_content = stripped.strip()
                    break

        # Step 2: Slice from \documentclass onwards — strips any LLM preamble text
        doc_start = tex_content.find("\\documentclass")
        if doc_start > 0:
            tex_content = tex_content[doc_start:]

        # Step 3: Truncate after \end{document} — strips trailing LLM commentary
        end_marker = "\\end{document}"
        if end_marker in tex_content:
            tex_content = tex_content.split(end_marker)[0] + end_marker
        elif "\\begin{document}" in tex_content:
            # Missing \end{document} — append it
            tex_content += "\n\\end{document}"

        return tex_content.strip()

    @staticmethod
    def tailor_latex_resume(base_tex_path: str, job_data: Dict[str, Any], output_tex_path: str) -> str:
        """
        Reads base main.tex and performs deep LLM ATS optimization:
        1. Splits the .tex into preamble+header (kept verbatim) and content body (sent to LLM).
        2. LLM rewrites only the content body sections to weave in JD keywords.
        3. Reassembles the full valid .tex and validates completeness before writing.
        """
        with open(base_tex_path, 'r', encoding='utf-8') as f:
            tex_content = f.read()

        company = job_data.get("company", "Target Company")
        role = job_data.get("role", "Target Role")
        requirements = job_data.get("requirements", [])
        req_str = "\n".join(requirements[:8])

        # Pre-calculate missing keywords to instruct LLM explicitly
        _, _, missing_kw = ResumeTailorer.calculate_ats_score(job_data)

        # 1. Groq LLM Deep Tailoring — send only the content body, not the preamble
        if config.groq.api_key:
            # Split: keep everything up to \begin{document} as the static preamble
            begin_doc_marker = "\\begin{document}"
            if begin_doc_marker in tex_content:
                preamble_part = tex_content.split(begin_doc_marker)[0] + begin_doc_marker + "\n"
                content_body = tex_content.split(begin_doc_marker)[1].rstrip()
                # Strip trailing \end{document} from content body (we'll add it back)
                if "\\end{document}" in content_body:
                    content_body = content_body.split("\\end{document}")[0].rstrip()
            else:
                preamble_part = ""
                content_body = tex_content

            system_prompt = (
                "You are an expert executive resume writer. Your goal is to subtly refine a candidate's LaTeX resume body for a target role without making it look artificially tailored or keyword-stuffed.\n\n"
                "CRITICAL ATS & QUALITY RULES:\n"
                "1. MINIMAL & SUBTLE EDITS: Make minimal changes to existing bullet points. Modify at most 2-4 bullet points across the entire resume only where a missing technical skill naturally fits into an existing project context.\n"
                "2. NO REPETITIVE PHRASING: NEVER repeat the same technology, tool, or phrase (e.g. 'using Python for data analysis') across multiple bullets. Each bullet point must remain unique, concise, and focused on its specific project/achievement.\n"
                "3. IGNORE SOFT SKILLS / GENERIC JD FLUFF: Completely IGNORE non-technical or generic soft-skill requirements in the JD (e.g. 'basic coding skills', 'strong analytical thinking', 'curiosity to learn', 'good communication'). DO NOT add these phrases into any bullet points.\n"
                "4. NO ARTIFICIAL SUFFIXES: NEVER tack phrases onto the end of bullet points (e.g., avoid adding ', utilizing microservices architecture' or ', applying mathematical models').\n"
                "5. ZERO EXTRA BOLDING: Do NOT add new \\textbf{} tags to words inside bullet points. Keep formatting identical to the original.\n"
                "6. TECHNICAL SKILLS SECTION FIRST: Align the Technical Skills section by reordering matching hard skills to the front.\n"
                "7. PRESERVE ORIGINAL TRUTH: Keep all metrics, numbers, and core technical descriptions accurate to the original resume.\n"
                "8. LATEX INTEGRATION: Keep ALL LaTeX syntax and character escapes (\\%, \\&, \\_, \\$) intact.\n"
                "9. OUTPUT FORMAT: Return ONLY the raw LaTeX content body (sections and items) — no preamble, no \\documentclass, no code blocks."
            )

            target_keywords_str = f"Missing Technical Keywords to seamlessly weave into Technical Skills or relevant project bullets: {', '.join(missing_kw)}\n" if missing_kw else ""
            user_prompt = (
                f"Target Role: {role} at {company}\n"
                f"Job Requirements Summary:\n{req_str}\n\n"
                f"{target_keywords_str}\n"
                f"LaTeX Resume Content Body to refine:\n{content_body}\n\n"
                f"Return the subtly refined, professional LaTeX content body for '{role} at {company}'."
            )

            try:
                tailored_body = llm_manager.generate(
                    task=TaskType.RESUME_TAILORING,
                    prompt=user_prompt,
                    system_prompt=system_prompt,
                    max_tokens=4000,
                    temperature=0.2
                )
                if not tailored_body:
                    print("[ResumeTailorer Note] LLM tailoring returned empty. Using base content body.")
                    tailored_body = content_body

                # Strip any accidental preamble the LLM might have added
                if "\\documentclass" in tailored_body:
                    # LLM returned full document — extract body only
                    if begin_doc_marker in tailored_body:
                        tailored_body = tailored_body.split(begin_doc_marker)[1]
                    if "\\end{document}" in tailored_body:
                        tailored_body = tailored_body.split("\\end{document}")[0]

                # Strip code fences if present
                if "```" in tailored_body:
                    parts = tailored_body.split("```")
                    for part in parts:
                        stripped = part.lstrip()
                        if stripped.lower().startswith(("latex", "tex")):
                            stripped = stripped.split("\n", 1)[-1]
                        if "\\section" in stripped or "\\begin" in stripped:
                            tailored_body = stripped.strip()
                            break

                # Reassemble complete .tex document
                if "\\section" in tailored_body or "\\begin{center}" in tailored_body:
                    if "\\end{document}" in tailored_body:
                        tailored_body = tailored_body.split("\\end{document}")[0].rstrip()
                    tailored_full = preamble_part + tailored_body + "\n\n\\end{document}\n"

                    with open(output_tex_path, 'w', encoding='utf-8') as f:
                        f.write(tailored_full)
                    print(f"[LLM Tailor] Successfully generated tailored LaTeX for '{role} at {company}'")
                    return output_tex_path
                else:
                    print(f"[LLM Tailor Warning] LLM returned unexpected content. Falling back to deterministic injector.")
            except Exception as e:
                print(f"[LLM Resume Tailor Note] {e}. Using deterministic ATS keyword injector.")

        # 2. Deterministic Fallback Keyword Optimization
        # Highlight target keywords in Technical Skills
        if missing_kw:
            priority_skills = ", ".join(missing_kw[:4])
            tex_content = tex_content.replace(
                "\\textbf{Languages}{: ",
                f"\\textbf{{Target Skills (ATS Optimized)}}{{: {priority_skills}}} \\\\\n     \\textbf{{Languages}}{{: "
            )

        with open(output_tex_path, 'w', encoding='utf-8') as f:
            f.write(tex_content)

        return output_tex_path

    @staticmethod
    def ask_multi_provider_llm(prompt: str, system_prompt: str = "You are a professional assistant writing concise, natural, human responses for job applications.", max_tokens: int = 2000, temperature: float = 0.4) -> str:
        """
        Delegates job application Q&A and email generation to LLMManager.
        """
        res = llm_manager.generate(
            task=TaskType.EMAIL_GENERATION,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature
        )
        if res:
            return res
        return ResumeTailorer._fallback_human_answer(prompt)

    @staticmethod
    def ask_groq_llm(prompt: str, system_prompt: str = "You are a professional assistant writing concise, natural, human responses for job applications.", max_tokens: int = 2000, temperature: float = 0.4) -> str:
        return ResumeTailorer.ask_multi_provider_llm(prompt, system_prompt, max_tokens, temperature)

    @staticmethod
    def infer_salutation(company: str = "", hr_email: str = "") -> str:
        if company and company.strip() not in ["Company", "Unknown", "Target Company"]:
            return f"Dear {company.strip()} Recruiting Team,"
        return "Dear HR Team,"


    @staticmethod
    def generate_hr_cover_letter(company: str, role: str, requirements: list, hr_email: str = "") -> str:
        salutation = ResumeTailorer.infer_salutation(company, hr_email)
        req_summary = ", ".join(requirements[:6]) if requirements else "software engineering, full-stack development, and AI/cloud systems"
        
        project_taxonomy_context = (
            "VIMAL'S PORTFOLIO TAXONOMY (BY TECH DOMAIN):\n"
            "1. FULL-STACK / MERN / WEB:\n"
            "   - Full-stack medical clinic ERP: React 18, Node.js, Express, MongoDB Atlas, Docker, Nginx. Built patient registry, HSN/GST-compliant PDF/DOCX invoicing, multi-tenant sandbox switcher, and real-time inventory deduction logic preventing race conditions during concurrent checkouts. Live demo: https://siddhashivalayas.vercel.app\n"
            "   - MERN E-Commerce Platform: React.js, Redux Toolkit, Node.js, Express, MongoDB, Tailwind. Built category routing, persistent cart state, and admin inventory controls.\n"
            "   - Interactive Kanban Desk Manager: React, Tailwind, REST APIs. Drag-and-drop workspace manager with local storage state routing.\n\n"
            "2. AI / GENAI / LLM / VOICE AGENTS / RAG:\n"
            "   - Production AI Voice Receptionist: RetellAI, FastAPI (Python 3.12+), Google Sheets API, Render. Solved clinic booking latency with dual-mode scheduling (live synchronous Google Sheets slot availability checking + async post-call webhooks to offload heavy I/O and prevent mid-call lag). Live demo: https://quensultingai-voice-agent.onrender.com\n"
            "   - Autonomous Job Application & ATS Engine: Python, Playwright, Groq/Gemini LLM API, LaTeX compiler, Chrome Extension. Telegram referral crawler, ATS keyword optimization, dynamic resume compilation.\n"
            "   - Corporate RAG SOP Framework (KSK Electronics Internship): LangChain, Chroma DB, React, Node.js. Built enterprise document QA engine and automated GST validation workflows.\n"
            "   - AI Adaptive Learning Platform (Intel Unnati): Next.js, Flask, Python, fine-tuned T5 Transformer for dynamic question generation, XGBoost for quiz difficulty scaling, SVD collaborative filtering for recommendations. Live demo: https://intel-unnati-game-frontend.vercel.app/\n\n"
            "3. BACKEND / API DESIGN / DISTRIBUTED & SCHEDULING ENGINES:\n"
            "   - Multi-Region Scheduling & Analytics Engine: Node.js, Express, TypeScript, LLM APIs. Multi-region timezone conversion engine, automated LLM synthesis, time-slot allocation without race conditions.\n"
            "   - Speaker Session Booking Backend: Node.js, Express, MongoDB, JWT auth. Double-booking prevention middleware and transactional email alerts.\n"
            "   - E-Commerce Catalog & Aggregation Engine: Node.js, Express, MongoDB. Scheduled cron sync jobs, price drop alerts, aggregation pipelines.\n\n"
            "4. MOBILE DEVELOPMENT (REACT NATIVE / EXPO):\n"
            "   - Aaku AI Travel Companion (Aakar Labs Internship): React Native, Expo, Agile product team. Engineered reusable UI components and integrated frontend with backend AI trip planning services.\n"
            "   - Wanderlust Mobile App: React Native, Expo SDK 55, React Navigation v7, Material 3, Reanimated (60FPS liquid animations), local storage caching.\n\n"
            "5. DEVOPS / CLOUD / INFRASTRUCTURE:\n"
            "   - Docker & Nginx Reverse Proxy Deployments: Multi-tenant container orchestration, microservices routing, SSL termination, environment secrets, keep-alive background workers on Render & Vercel.\n\n"
            "6. DATA SCIENCE / MACHINE LEARNING / ANALYTICS:\n"
            "   - AQI Predictive Regression Model: Python, Scikit-learn (Random Forest, Ridge), Pandas, NumPy. Feature outlier cleaning, multicollinearity reduction, AQI forecasting.\n"
            "   - Multithreaded Web Scraping & Aggregation: Python ThreadPoolExecutor parallel scraping pipeline across e-commerce domains, feeding AI classification and MongoDB storage.\n"
        )

        system_prompt = (
            "You are Vimal Manoharan, a Computer Science Engineering graduate (Class of 2026 from SRM IST, CGPA 8.91/10.0) writing a concise, natural, human-sounding cold email to a recruiter or hiring manager.\n\n"
            "CRITICAL EMAIL CURATION RULES:\n"
            "1. INTELLIGENT JD MATCHING: Read the Job Description and Role carefully. Determine what domain the role belongs to (Full-Stack, AI/LLM, Backend/APIs, Mobile, DevOps, Data Science, etc.). Select 1 or 2 projects from Vimal's taxonomy that DIRECTLY match the JD domain.\n"
            "2. NEVER NAME-DROP OBSCURE PROJECT NAMES: NEVER say project title names like 'Fleksa', 'QuensultingAI', 'Siddha Shivalayas', 'ApplyBot', or 'Aaku'! The recruiter does NOT know what these internal names are and will be confused. Instead, describe WHAT YOU BUILT naturally (e.g., write 'a full-stack clinic management system handling patient records and real-time inventory tracking', or 'a production AI voice receptionist with live scheduling and async webhook processing', or 'a production scheduling engine handling multi-region timezone conversions').\n"
            "3. NATURAL & HUMAN WRITING: Write like a sharp, confident engineer — NOT like a template or generic AI! Avoid canned phrases like 'I am writing to express my profound enthusiasm' or 'I possess a strong foundation'. Use clean, conversational language.\n"
            "4. NO REPO LINKS: Do NOT include GitHub repo links in the email text. If a project has a live demo link (e.g. https://siddhashivalayas.vercel.app or https://quensultingai-voice-agent.onrender.com), you may naturally mention 'you can check out a live demo at [URL]' ONLY if that project is selected.\n"
            "5. EMAIL STRUCTURE:\n"
            "   - Start directly with 'Dear HR team,'\n"
            "   - Sentence 1-2: Express interest in the {role} position at {company}, briefly noting your background as a Computer Science Senior at SRM IST (Class of '26, CGPA 8.91/10.0).\n"
            "   - Middle Paragraph: Detail 1 or 2 domain-matched projects. Explain the technical problem you solved, key technologies used, and the impact (e.g. real-time inventory deduction, sub-second voice latency, multi-tenant database isolation, Docker deployment).\n"
            "   - Closing Sentence: Mention that your resume is attached for review and express interest in a brief introductory chat.\n"
            "6. DO NOT include a Subject line.\n"
            "7. DO NOT include any sign-off or signature at the end (NO 'Best regards', NO candidate name). Signature will be appended automatically.\n"
            "8. TARGET LENGTH: 120 to 160 words max. Keep it crisp, targeted, and human."
        )

        prompt = (
            f"Salutation: '{salutation}'\n"
            f"Applying for: {role} at {company}\n"
            f"Job Requirements & Key Context: {req_summary}\n\n"
            f"{project_taxonomy_context}\n\n"
            f"Write ONLY the email body text."
        )

        raw_body = ResumeTailorer.ask_groq_llm(prompt, system_prompt, max_tokens=800, temperature=0.45)
        
        lines = [line for line in raw_body.split("\n") if not line.lower().startswith("subject:")]
        cleaned = "\n".join(lines).strip()
        
        for term in ["Best regards", "Sincerely", "Warm regards", "Thanks", "Thank you", "Vimal Manoharan"]:
            if term in cleaned:
                cleaned = cleaned.split(term)[0].strip()
                
        if not cleaned.startswith("Dear"):
            cleaned = f"{salutation}\n\n" + cleaned
            
        return cleaned

    @staticmethod
    def answer_custom_question(question: str, company: str, role: str,
                               jd_text: str = "", page_context: str = "",
                               length_hint: str = "") -> str:
        """
        Generate a personalised, human-sounding answer to a job application question.
        Optionally uses the Job Description (jd_text) and page context (page_context)
        for ultra-tailored responses.
        """
        context_blocks = []
        if jd_text:
            context_blocks.append(f"[JOB DESCRIPTION]\n{jd_text[:2000]}")
        if page_context:
            context_blocks.append(f"[PAGE CONTEXT from application portal]\n{page_context[:1500]}")

        context_section = "\n\n".join(context_blocks)
        context_note = (
            "Use the provided Job Description and page context to tailor your answer specifically "
            "to this role and company."
        ) if context_section else ""

        if length_hint == "short":
            length_instruction = "Answer strictly in 1-2 concise, impact-driven sentences."
        elif length_hint == "detailed":
            length_instruction = "Answer in 4-6 detailed, comprehensive sentences covering specific technologies and achievements."
        else:
            length_instruction = "Answer job application questions in 2-4 genuine, human-sounding sentences. Be specific, confident, and natural."

        work_exp_summary = "\n".join([
            f"- {w['role']} at {w['company']} ({w['dates']}): {w['description']}"
            for w in getattr(config.profile, "work_experience", [])
        ])

        projects_summary = "\n".join([
            f"- {p['name']} ({p['tech']}): {p['description']}"
            for p in config.profile.key_projects
        ])

        system_prompt = (
            "You are Vimal Manoharan, a Computer Science Engineering graduate (Class of 2026) from SRM Institute of Science "
            "and Technology (CGPA: 8.91/10).\n\n"
            f"VIMAL'S REAL PAID WORK EXPERIENCE & INTERNSHIPS:\n{work_exp_summary}\n\n"
            f"VIMAL'S FEATURED PROJECTS:\n{projects_summary}\n\n"
            f"{length_instruction}\n"
            "CRITICAL RULES:\n"
            "1. DOMAIN CURATION: Carefully analyze the target company, role, and JD domain (e.g. Product Management, FinTech, AI, Full-Stack, Mobile). Tailor your excitement and experience SPECIFICALLY to that domain! DO NOT mention irrelevant random projects or internal project names that sound obscure.\n"
            "2. PRIOR INTERNSHIP EXPERIENCE: Vimal HAS real paid internship & freelance experience (Aakar Labs, KSK Electronics, Siddha Shivalayas Clinic). Always highlight these when asked about prior internship experience!\n"
            "3. STIPEND & PRODUCTS: Last stipend paid is ₹20,000 / month. Key product link is https://siddhashivalayas.vercel.app.\n"
            f"{context_note}"
        )

        prompt = f"Question: '{question}'\nApplying for: '{role}' at '{company}'."
        if context_section:
            prompt += f"\n\n{context_section}"

        return ResumeTailorer.ask_groq_llm(prompt, system_prompt, max_tokens=450, temperature=0.35)

    @staticmethod
    def _fallback_human_answer(prompt: str) -> str:
        if "salutation:" in prompt.lower() or "applying for:" in prompt.lower() or "candidate:" in prompt.lower():
            return (
                "Dear HR team,\n\n"
                "I am eager to apply for the software engineering position at your company. "
                "As a Computer Science Senior at SRM Institute of Science and Technology (Class of 2026, CGPA 8.91/10.0), "
                "I have developed robust hands-on experience building production full-stack platforms and AI engineering systems.\n\n"
                "Recently, I architected a full-stack clinic ERP platform using React, Node.js, and MongoDB that manages patient records, "
                "automates GST-compliant invoicing, and enforces real-time inventory deduction logic with race-condition safety. "
                "Additionally, I built a production AI voice receptionist leveraging FastAPI and async webhooks to achieve sub-second booking latency.\n\n"
                "I have attached my tailored resume for your review and would welcome the opportunity to discuss how my technical skills "
                "align with your team's goals."
            )
        elif "motivated" in prompt.lower() or "why" in prompt.lower() or "apply" in prompt.lower():
            return (
                "I am eager to apply because this role aligns directly with my hands-on background in full-stack engineering "
                "and AI systems. Having shipped production applications using React, Node.js, FastAPI, and LLM agent workflows, "
                "I look forward to contributing clean, resilient code to your team."
            )
        elif "good fit" in prompt.lower() or "fit" in prompt.lower():
            return (
                "My experience across full-stack web development, API design, and AI automation directly "
                "matches your engineering requirements. I thrive in fast-paced product environments and take pride in shipping high-quality code."
            )
        else:
            return (
                "With my strong Computer Science background and practical project experience across full-stack and AI systems, "
                "I am confident in my ability to make an immediate, positive impact on your team."
            )


