import sys
import os
import time
import json
import urllib.request
from playwright.sync_api import sync_playwright
from config import config

if len(sys.argv) < 5:
    print("Error: Missing parameters")
    sys.exit(1)

url = sys.argv[1]
action_plan = json.loads(sys.argv[2])
pdf_path = sys.argv[3]
profile = json.loads(sys.argv[4])
job_data = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}

def inspect_and_generate_live_plan(page, job_data, profile):
    """
    Inspects live DOM elements directly inside the open Chrome window
    and calls Groq LLM to generate answers for all fields.
    """
    fields = []
    elements = page.query_selector_all("input:not([type='hidden']), textarea, select")
    for idx, el in enumerate(elements):
        if not el.is_visible():
            continue
        t = el.get_attribute("type") or el.evaluate("el => el.tagName")
        name = el.get_attribute("name") or ""
        aria_label = (el.get_attribute("aria-label") or "").strip()
        placeholder = (el.get_attribute("placeholder") or "").strip()
        id_attr = (el.get_attribute("id") or "").strip()
        
        label = ""
        if aria_label and aria_label.lower() not in ["your answer", "option 1", "short answer text", "long answer text"]:
            label = aria_label
        elif placeholder and placeholder.lower() not in ["your answer", "option 1"]:
            label = placeholder
            
        if not label:
            try:
                container = el.evaluate_handle("el => el.closest('div[role=\"listitem\"], div[jsmodel], fieldset, label')")
                if container:
                    heading = container.evaluate("""c => {
                        const h = c.querySelector('div[role="heading"], legend, .M7eF9, .hoP2b, h1, h2, h3, h4');
                        if (h && h.innerText) return h.innerText;
                        return c.innerText;
                    }""")
                    if heading:
                        lines = [line.strip() for line in heading.split('\n') if line.strip() and line.strip() != '*']
                        if lines:
                            label = lines[0]
            except Exception:
                pass
                
        if not label:
            label = aria_label or placeholder or name or id_attr or f"Field_{idx}"

        fields.append({
            "index": idx,
            "type": t,
            "name": name,
            "label": label.strip(),
            "id": id_attr
        })

    radio_questions = []
    q_blocks = page.query_selector_all("div[role='listitem']")
    for q_idx, q in enumerate(q_blocks):
        txt = q.evaluate("el => el.innerText")
        if txt:
            lines = [l.strip() for l in txt.split('\n') if l.strip()]
            if len(lines) >= 2:
                q_title = lines[0]
                options = lines[1:]
                radio_questions.append({
                    "question_index": q_idx,
                    "question": q_title,
                    "options": options
                })

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
        "Vimal has strong technical skills in AI Agents, LangChain, RAG pipelines, React Native, Node.js, FastAPI, "
        "Python, and product development strategy.\n\n"
        "Candidate Profile:\n"
        f"- Full Name: {config.profile.full_name}\n"
        f"- Email: {config.profile.email}\n"
        f"- Phone: {config.profile.phone}\n"
        f"- Location: {config.profile.location}\n"
        f"- University: {config.profile.university}\n"
        f"- Degree: {config.profile.degree}\n"
        f"- CGPA: {config.profile.gpa}\n"
        f"- Graduation Year: {config.profile.graduation_year}\n"
        f"- LinkedIn: {config.profile.linkedin_url}\n"
        f"- GitHub/Portfolio: {config.profile.github_url}\n"
        f"- Resume Link: {config.profile.resume_gdrive_url}\n"
        f"- Core Skills: {', '.join(config.profile.core_skills)}\n\n"
        f"VIMAL'S FEATURED GITHUB PROJECTS:\n{projects_summary}\n\n"
        "RULES FOR DYNAMIC FORM FILLING:\n"
        "1. Standard profile fields (Name, Email, Phone, Location, College, CGPA, Batch, Links): fill with exact candidate profile values.\n"
        "2. Custom / Subjective / Essay / Strategy / Project questions: Generate a highly relevant, impressive, natural human-sounding answer (2-5 sentences or structured points). You have full access to Vimal's entire GitHub project portfolio above. Intelligently select the SINGLE BEST project (or combination) that aligns most strongly with the target role and specific question! For example: for Voice/AI/Speech/Backend roles, select QuensultingAI Voice Agent; for Healthcare/Full-Stack SaaS, select Siddha Shivalayas; for GenAI/LLM, select Intel Unnati; for Mobile/Product/UI, select Wanderlust; for Automation, select ApplyBot. Always include repo links, tech stack details, and real impact! Answer EVERY field!\n"
        "3. Radio / Choice questions: Select the exact option string that best fits Vimal's background.\n\n"
        "Output ONLY a valid JSON array of objects matching this exact schema (no Markdown wrappers outside JSON):\n"
        "[\n"
        '  {"index": 0, "action": "fill", "label": "question text", "value": "answer text"},\n'
        '  {"index": 1, "action": "click_option", "label": "question text", "value": "exact option text"}\n'
        "]"
    )

    user_prompt = (
        f"Applying for: {role} at {company}\n"
        f"Job Description / Post:\n{raw_text[:3500]}\n\n"
        f"Form Fields List:\n{json.dumps(fields, indent=2)}\n\n"
        f"Radio Questions List:\n{json.dumps(radio_questions, indent=2)}\n\n"
        "Generate the JSON array of actions for EVERY input field and radio question above."
    )

    if not config.groq.api_key:
        return []

    try:
        url_api = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.groq.api_key}"
        }
        payload = {
            "model": config.groq.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.3
        }
        req = urllib.request.Request(url_api, data=json.dumps(payload).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            llm_res = res_data["choices"][0]["message"]["content"].strip()
            if "```" in llm_res:
                parts = llm_res.split("```")
                for p in parts:
                    if "[" in p and "]" in p:
                        llm_res = p.replace("json", "").strip()
                        break
            return json.loads(llm_res.strip())
    except Exception as e:
        print(f"[Live Groq Action Plan Error] {e}")
        return []

user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_profile")
os.makedirs(user_data_dir, exist_ok=True)

# Remove profile locks if present
for lock in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
    f_path = os.path.join(user_data_dir, lock)
    if os.path.exists(f_path) or os.path.islink(f_path):
        try:
            os.remove(f_path)
        except Exception:
            pass

print(f"⚡ [ApplyBot Stealth Engine] Opening system Google Chrome for {url}...")

with sync_playwright() as p:
    try:
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ],
            ignore_default_args=["--enable-automation"]
        )
    except Exception as ex:
        print(f"[Stealth Launch Note] Persistent profile in use ({ex}). Launching direct Chrome window...")
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context()
    
    page = context.pages[0] if context.pages else context.new_page()
    
    try:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        # Inspect page live if action plan is insufficient
        all_inputs = page.query_selector_all("input:not([type='hidden']), textarea, select")
        visible_inputs = [el for el in all_inputs if el.is_visible()]
        if len(action_plan) < len(visible_inputs):
            print(f"⚡ [ApplyBot Stealth Engine] Live page has {len(visible_inputs)} visible fields. Generating real-time AI Action Plan...")
            live_plan = inspect_and_generate_live_plan(page, job_data, profile)
            if live_plan:
                action_plan = live_plan
        
        # 1. Execute LLM Action Plan with Multi-Strategy Element Matching
        all_inputs = page.query_selector_all("input:not([type='hidden']), textarea, select")
        
        for item in action_plan:
            action = item.get("action")
            label = item.get("label", "")
            val = item.get("value", "")
            idx = item.get("index")
            
            try:
                if action == "fill" and val:
                    filled = False
                    
                    # Strategy 1: Match by direct element index if valid
                    if idx is not None and isinstance(idx, int) and 0 <= idx < len(all_inputs):
                        target_el = all_inputs[idx]
                        if target_el and target_el.is_visible():
                            target_el.fill(str(val))
                            target_el.dispatch_event("input")
                            target_el.dispatch_event("change")
                            target_el.dispatch_event("blur")
                            page.wait_for_timeout(200)
                            filled = True
                            
                    # Strategy 2: Google Form / Web Form item container matching
                    if not filled and label:
                        containers = page.query_selector_all("div[role='listitem'], div[jsmodel], div.geFormItem, fieldset, label")
                        for container in containers:
                            c_text = container.evaluate("el => el.innerText") or ""
                            if label.lower()[:30] in c_text.lower():
                                inp = container.query_selector("input:not([type='hidden']), textarea")
                                if inp and inp.is_visible():
                                    inp.fill(str(val))
                                    inp.dispatch_event("input")
                                    inp.dispatch_event("change")
                                    inp.dispatch_event("blur")
                                    page.wait_for_timeout(200)
                                    filled = True
                                    break
                                    
                    # Strategy 3: Standard Playwright get_by_label / get_by_placeholder
                    if not filled and label:
                        el = page.get_by_label(label, exact=False).first
                        if not el or not el.is_visible():
                            el = page.get_by_placeholder(label, exact=False).first
                        if el and el.is_visible():
                            el.fill(str(val))
                            el.dispatch_event("input")
                            el.dispatch_event("change")
                            el.dispatch_event("blur")
                            page.wait_for_timeout(200)

                elif action == "click_option" and val:
                    elem = page.get_by_text(str(val), exact=False).first
                    if elem and elem.is_visible():
                        elem.click()
                        page.wait_for_timeout(200)
            except Exception as e:
                print(f"[Action Step Error] {e}")
                
        # 2. General Profile Auto-Filler Fallback
        try:
            for el in page.query_selector_all("input:not([type='hidden']), textarea"):
                if not el.is_visible():
                    continue

                val_curr = ""
                try:
                    val_curr = el.input_value().strip()
                except Exception:
                    pass

                if val_curr:
                    continue

                label = (el.get_attribute("aria-label") or el.get_attribute("placeholder") or el.get_attribute("name") or el.get_attribute("id") or "").lower()
                try:
                    parent = el.evaluate_handle("el => el.closest('div[role=\"listitem\"], label, fieldset')")
                    if parent:
                        lbl_t = parent.evaluate("el => el.innerText")
                        if lbl_t:
                            label = (label + " " + lbl_t).lower()
                except Exception:
                    pass

                if "email" in label:
                    el.fill(profile["email"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "location" in label or "city" in label or "address" in label:
                    el.fill(profile.get("location", "Chennai, Tamil Nadu, India"))
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "first name" in label:
                    el.fill(profile["first_name"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "last name" in label:
                    el.fill(profile["last_name"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "name" in label and "company" not in label and "user" not in label and "file" not in label:
                    el.fill(profile["name"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "phone" in label or "mobile" in label or "contact" in label:
                    el.fill(profile["phone"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif ("resume" in label and ("link" in label or "url" in label or "drive" in label)) or "gdrive" in label:
                    el.fill(profile["resume_gdrive_url"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "linkedin" in label:
                    el.fill(profile["linkedin"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "github" in label or "portfolio" in label or "website" in label:
                    el.fill(profile["github"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "college" in label or "university" in label or "institute" in label:
                    el.fill(profile["college"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "degree" in label or "branch" in label or "major" in label:
                    el.fill(profile["degree"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "gpa" in label or "cgpa" in label or "marks" in label:
                    el.fill(profile["gpa"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "graduat" in label or "batch" in label or "year" in label:
                    el.fill(profile["grad_year"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                        
            # File upload for Resume
            if pdf_path and os.path.exists(pdf_path):
                file_inputs = page.query_selector_all("input[type='file']")
                if file_inputs:
                    file_inputs[0].set_input_files(pdf_path)
                    page.wait_for_timeout(500)
        except Exception as e:
            print(f"[Stealth Chrome Auto-Fill Note] {e}")

        print("⚡ [ApplyBot Stealth Engine] Form auto-filled! Chrome window open for manual review & submit...")
        time.sleep(600)
    except Exception as e:
        print(f"[Playwright Stealth Error] {e}")
