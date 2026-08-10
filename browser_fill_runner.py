import sys
import os
import time
import json
import urllib.request
import traceback
from datetime import datetime
from playwright.sync_api import sync_playwright
from config import config

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "applybot_fill.log")

def log(msg):
    """Write to both stdout and log file."""
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# Clear previous log
try:
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== ApplyBot Fill Log - {datetime.now()} ===\n")
except Exception:
    pass

if len(sys.argv) < 5:
    log("Error: Missing parameters")
    sys.exit(1)

url = sys.argv[1]
action_plan = json.loads(sys.argv[2])
pdf_path = sys.argv[3]
profile = json.loads(sys.argv[4])
job_data = json.loads(sys.argv[5]) if len(sys.argv) > 5 else {}

log(f"URL: {url}")
log(f"Initial action_plan size: {len(action_plan)}")
log(f"job_data keys: {list(job_data.keys())}")
log(f"job_data company: {job_data.get('company', 'N/A')}")
log(f"job_data role: {job_data.get('role', 'N/A')}")
log(f"job_data raw_text length: {len(job_data.get('raw_text', ''))}")
log(f"Groq API key present: {bool(config.groq.api_key)}")
log(f"Groq model: {config.groq.model_name}")
log(f"Projects count: {len(config.profile.key_projects)}")

def inspect_and_generate_live_plan(page, job_data, profile):
    """
    Inspects live DOM elements directly inside the open Chrome window
    and calls Groq LLM to generate answers for all fields.
    """
    log("--- inspect_and_generate_live_plan START ---")
    
    fields = []
    INPUT_SEL = "input:not([type='hidden']):not([type='radio']):not([type='checkbox']):not([type='submit']):not([type='button']):not([type='image']), textarea, select"
    elements = page.query_selector_all(INPUT_SEL)
    log(f"Main page input/textarea/select elements found: {len(elements)}")
    
    # Deep Inspection: If 0 visible elements found, check iframes or click Apply/Next button
    if not elements or not any(e.is_visible() for e in elements):
        log("No visible inputs found on main page! Checking iframe frames & looking for Apply/Next button...")
        
        # 1. Search frames
        for frame in page.frames:
            try:
                f_elems = frame.query_selector_all(INPUT_SEL)
                if f_elems and any(fe.is_visible() for fe in f_elems):
                    log(f"Found {len(f_elems)} inputs in iframe: {frame.url}")
                    elements = f_elems
                    break
            except Exception:
                pass

        # 2. Click Apply/Apply Now/Next button if still 0
        if not elements or not any(e.is_visible() for e in elements):
            try:
                apply_btn = page.query_selector("button:has-text('Apply'), a:has-text('Apply'), div[role='button']:has-text('Apply'), span:has-text('Apply'), button:has-text('Next'), span:has-text('Next')")
                if apply_btn and apply_btn.is_visible():
                    log(f"Found Apply/Next button on page! Clicking to reveal form...")
                    apply_btn.click()
                    page.wait_for_timeout(2500)
                    elements = page.query_selector_all(INPUT_SEL)
            except Exception as btn_ex:
                log(f"Error clicking Apply button: {btn_ex}")

    visible_count = 0
    for idx, el in enumerate(elements):
        if not el.is_visible():
            continue
        visible_count += 1
        
        # Skip "Other response" text inputs (belong to radio "Other:" options)
        _aria_lbl = (el.get_attribute("aria-label") or "").strip().lower()
        if _aria_lbl in ["other response", "other"]:
            log(f"  [Field {idx}] SKIPPED (Other response radio text input)")
            continue
        
        # Skip inputs inside a radiogroup container
        try:
            inside_radio = el.evaluate("el => !!el.closest('div[role=\"radiogroup\"], div[role=\"group\"]')")
            if inside_radio:
                log(f"  [Field {idx}] SKIPPED (inside radiogroup)")
                continue
        except Exception:
            pass
        
        t = el.get_attribute("type") or el.evaluate("el => el.tagName")
        name = el.get_attribute("name") or ""
        id_attr = (el.get_attribute("id") or "").strip()
        
        # Single JS expression to extract the real question title
        try:
            lbl = el.evaluate("""el => {
                const isGuid = (s) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test((s || '').trim());
                
                // 1. Parent Tally / ATS block container heading
                const blockContainer = el.closest('.tally-block, div[data-block-id], div[role="listitem"], .form-group, .field, fieldset, label, div[class*="block"], div[class*="input"], div[class*="field"]');
                if (blockContainer) {
                    const heading = blockContainer.querySelector('h1, h2, h3, h4, label, legend, div[role="heading"], .tally-text-block, .M7eF9, .hoP2b, .field-label, p');
                    if (heading && heading.innerText) {
                        const lines = heading.innerText.split("\\n").map(l => l.trim()).filter(l => l && l !== '*' && !isGuid(l));
                        if (lines.length > 0 && lines[0].length < 250 && !isGuid(lines[0])) return lines[0];
                    }
                }
                
                // 2. Associated <label for="id"> or preceding label
                if (el.id) {
                    const lblEl = document.querySelector(`label[for="${el.id}"]`);
                    if (lblEl && lblEl.innerText && lblEl.innerText.trim() && !isGuid(lblEl.innerText.trim())) return lblEl.innerText.trim();
                }
                
                // 3. Aria-label
                const aria = (el.getAttribute('aria-label') || '').trim();
                if (aria && !['your answer', 'option 1', 'short answer text', 'long answer text', 'enter here'].includes(aria.toLowerCase()) && !isGuid(aria)) return aria;
                
                // 4. Placeholder
                const ph = (el.getAttribute('placeholder') || '').trim();
                if (ph && !['your answer', 'option 1', 'enter here'].includes(ph.toLowerCase()) && !isGuid(ph)) return ph;
                
                // 5. Name / ID (only if NOT a UUID/GUID)
                const name = (el.getAttribute('name') || el.getAttribute('id') || '').trim();
                if (name && !isGuid(name)) return name;
                
                return el.type || '';
            }""")
        except Exception as ex:
            log(f"  JS evaluate error for element {idx}: {ex}")
            lbl = ""
        
        label_str = (lbl or f"Field_{idx}").strip()
        log(f"  [Field {idx}] vis=True type={t} label='{label_str[:80]}'")
        
        fields.append({
            "index": idx,
            "type": t,
            "name": name,
            "label": label_str,
            "id": id_attr
        })

    log(f"Visible input fields found: {visible_count}, captured: {len(fields)}")

    radio_questions = []
    q_blocks = page.query_selector_all("div[role='listitem'], .form-group, fieldset, div[role='radiogroup']")
    log(f"Choice blocks found: {len(q_blocks)}")
    for q_idx, q in enumerate(q_blocks):
        # Process blocks that contain radio, checkbox, or dropdown/combobox controls
        try:
            has_radio = q.query_selector(
                "div[role='radio'], div[role='checkbox'], input[type='radio'], "
                "input[type='checkbox'], div[role='radiogroup'], div[role='listbox'], "
                "div[role='combobox'], select, .v8y8e"
            )
        except Exception:
            has_radio = None
        if not has_radio:
            continue
        
        # Extract question title from heading element
        try:
            q_title = q.evaluate("""el => {
                const heading = el.querySelector('label, div[role="heading"], legend, .M7eF9, .hoP2b, .field-label, h1, h2, h3, h4');
                if (heading && heading.innerText) {
                    return heading.innerText.split("\\n").map(l => l.trim()).filter(l => l && l !== '*')[0] || '';
                }
                return '';
            }""")
        except Exception:
            q_title = ""
        if not q_title:
            continue
        
        # Extract option labels from radio/checkbox/dropdown elements
        try:
            options = q.evaluate("""(el) => {
                const opts = [];
                const controls = el.querySelectorAll('div[role="radio"], div[role="checkbox"], div[role="option"], option');
                controls.forEach(r => {
                    const dataVal = r.getAttribute('data-value') || r.getAttribute('value');
                    const txt = r.innerText ? r.innerText.trim() : '';
                    if (dataVal && dataVal !== '__other_option__' && dataVal !== '') {
                        opts.push(dataVal);
                    } else if (txt && txt !== '*' && txt !== 'Choose') {
                        opts.push(txt);
                    }
                });
                
                // Fallback for closed dropdowns (listbox / combobox)
                const listbox = el.querySelector('div[role="listbox"], div[role="combobox"], select, .v8y8e');
                if (listbox && opts.length === 0) {
                    try {
                        listbox.click();
                        const openOpts = document.querySelectorAll('div[role="option"], .exportOption');
                        openOpts.forEach(o => {
                            const txt = (o.innerText || o.textContent || '').trim();
                            if (txt && txt !== 'Choose' && txt !== '*' && !opts.includes(txt)) {
                                opts.push(txt);
                            }
                        });
                        document.body.click();
                    } catch (e) {}
                }
                return opts;
            }""")
        except Exception:
            options = []
        
        # Fallback: extract from container text
        if not options:
            try:
                txt = q.evaluate("el => el.innerText") or ""
                lines = [l.strip() for l in txt.split('\n') if l.strip() and l.strip() != '*' and l.strip() != q_title]
                options = lines
            except Exception:
                pass
        
        if options:
            radio_questions.append({
                "question_index": q_idx,
                "question": q_title,
                "options": options
            })
            log(f"  [Choice Q{q_idx}] '{q_title[:60]}' => options: {options[:5]}")

    log(f"Choice/Radio/Dropdown question blocks: {len(radio_questions)}")

    if not fields and not radio_questions:
        log("WARNING: No fields AND no radio questions found! Returning empty plan.")
        return []

    company = job_data.get("company", "Company")
    role = job_data.get("role", "Role")
    raw_text = job_data.get("raw_text", "")
    log(f"Job context: company='{company}', role='{role}', raw_text_len={len(raw_text)}")

    projects_summary = "\n".join([
        f"- {p['name']} ({p['tech'][:40]}): {p['description'][:120]} [Live Demo / Repo: {p.get('live_demo') or p['url']}]"
        for p in config.profile.key_projects[:8]
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
        f"- First Name: {config.profile.first_name}, Last Name: {config.profile.last_name}\n"
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
        "   - For text input fields: use action='fill', set 'index', and set 'label' to the field label text.\n"
        "   - For radio/checkbox/dropdown choice questions: use action='click_option', set 'question_index', set 'label' to the question title, and set 'value' to an EXACT option string listed.\n"
        "   - ALWAYS include the non-empty 'label' string in every object!\n\n"
        "Output ONLY a valid JSON array matching this exact format:\n"
        '[\n'
        '  {"index": 0, "action": "fill", "label": "Name", "value": "Vimal Manoharan"},\n'
        '  {"question_index": 5, "action": "click_option", "label": "Highest Qualification", "value": "B.Tech"}\n'
        ']'
    )

    user_prompt = (
        f"Applying for: {role} at {company}\n"
        f"Job Summary: {raw_text[:800]}\n\n"
        f"=== TEXT INPUT FIELDS (use action='fill', reference by 'index') ===\n{json.dumps(fields, indent=2)}\n\n"
        f"=== RADIO/CHOICE QUESTIONS (use action='click_option', reference by 'question_index') ===\n{json.dumps(radio_questions, indent=2)}\n\n"
        "Generate a JSON array with actions for ALL text fields AND ALL radio questions."
    )

    providers = getattr(config.multi_llm, "providers", [])
    
    for p in providers:
        p_name = p.get("name", "LLM")
        env_var = p.get("api_key_env", "")
        raw_key = os.getenv(env_var, getattr(config.multi_llm, f"{p_name.lower()}_api_key", ""))
        api_key = (raw_key or "").strip().strip('"').strip("'")
        
        if not api_key:
            log(f"Skipping {p_name}: No API key set for {env_var}")
            continue
            
        models = p.get("models", [])
        
        for model_candidate in models:
            log(f"Calling {p_name} API ({model_candidate}): system_prompt_len={len(system_prompt)}, user_prompt_len={len(user_prompt)}")
            
            try:
                if p_name == "Gemini":
                    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_candidate}:generateContent?key={api_key}"
                    payload = {
                        "contents": [{
                            "parts": [{"text": f"SYSTEM: {system_prompt}\n\nUSER: {user_prompt}"}]
                        }]
                    }
                    req_data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(gemini_url, data=req_data, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=30) as response:
                        res_bytes = response.read()
                        res_data = json.loads(res_bytes.decode("utf-8"))
                        llm_res = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                else:
                    endpoint = p.get("endpoint")
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                        "User-Agent": "ApplyBot/1.0"
                    }
                    if p_name == "OpenRouter":
                        headers["HTTP-Referer"] = "https://github.com/vimal004/ApplyBot"
                        headers["X-Title"] = "ApplyBot"
                        
                    payload = {
                        "model": model_candidate,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 2000
                    }
                    req_data = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(endpoint, data=req_data, headers=headers)
                    with urllib.request.urlopen(req, timeout=30) as response:
                        res_bytes = response.read()
                        res_data = json.loads(res_bytes.decode("utf-8"))
                        llm_res = res_data["choices"][0]["message"]["content"].strip()
                    
                log(f"LLM response received from {p_name}/{model_candidate} ({len(llm_res)} chars)")
                
                # Robust JSON array extraction
                start_idx = llm_res.find("[")
                end_idx = llm_res.rfind("]")
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    llm_res = llm_res[start_idx:end_idx+1]
                elif "```" in llm_res:
                    parts = llm_res.split("```")
                    for part in parts:
                        if "[" in part and "]" in part:
                            llm_res = part.replace("json", "").strip()
                            break
                
                plan = json.loads(llm_res.strip())
                log(f"Parsed action plan from {p_name}: {len(plan)} actions")
                for a in plan:
                    log(f"  Plan: action={a.get('action')}, label='{str(a.get('label',''))[:40]}', value='{str(a.get('value',''))[:50]}'")
                return plan
            except urllib.error.HTTPError as e:
                error_body = e.read().decode("utf-8") if e.fp else "N/A"
                log(f"{p_name} API HTTP Error {e.code} on model {model_candidate}: {error_body[:200]}")
                time.sleep(1)
                continue
            except Exception as e:
                log(f"{p_name} API Error on model {model_candidate}: {e}")
                continue

    log("WARNING: Groq API rate limited / unavailable. Executing Local Deterministic Heuristic Plan Generator...")
    fallback_plan = []
    
    # 1. Fill Actions for fields
    for f in fields:
        idx = f.get("index")
        lbl = f.get("label", "").lower()
        f_name = f.get("name", "").lower()
        f_id = f.get("id", "").lower()
        f_type = f.get("type", "").lower()
        val = ""
        
        if "email" in lbl or "email" in f_name or "email" in f_type or "@" in lbl:
            val = profile.get("email", config.profile.email)
        elif "first" in lbl or "fname" in lbl or "first_name" in f_name or lbl == "tony":
            val = profile.get("first_name", config.profile.first_name)
        elif "last" in lbl or "lname" in lbl or "last_name" in f_name or lbl == "jordan":
            val = profile.get("last_name", config.profile.last_name)
        elif "phone" in lbl or "mobile" in lbl or "contact" in lbl or "tel" in f_type or "+91" in lbl or "phone" in f_name:
            val = profile.get("phone", config.profile.raw_phone)
        elif "country" in lbl or "united states" in lbl:
            val = "India"
        elif "location" in lbl or "city" in lbl or "address" in lbl or "street" in lbl or "pune" in lbl or "new york" in lbl:
            val = profile.get("location", config.profile.location)
        elif "linkedin" in lbl or "linkedin" in f_name:
            val = profile.get("linkedin", config.profile.linkedin_url)
        elif "github" in lbl or "portfolio" in lbl or "website" in lbl or "github" in f_name:
            val = profile.get("github", config.profile.github_url)
        elif "college" in lbl or "university" in lbl or "institute" in lbl:
            val = profile.get("college", config.profile.university)
        elif "degree" in lbl or "branch" in lbl or "major" in lbl:
            val = profile.get("degree", config.profile.degree)
        elif "gpa" in lbl or "cgpa" in lbl or "marks" in lbl:
            val = profile.get("gpa", config.profile.gpa)
        elif "stipend" in lbl or "salary" in lbl or "ctc" in lbl:
            val = getattr(config.profile, "last_stipend", "20,000 / month")
        elif "impact" in lbl or "company" in lbl:
            val = "Siddha Shivalayas Clinic (https://siddhashivalayas.vercel.app)"
        elif "product" in lbl or "link" in lbl or "app store" in lbl or "weblink" in lbl:
            val = "https://siddhashivalayas.vercel.app"
        elif "prior" in lbl or "internship" in lbl or "experience" in lbl:
            val = "React Native Frontend Developer Intern at Aakar Labs (7 months, Aaku AI travel companion) and Software Developer Intern at KSK Electronics (3 months, full-stack ERP & RAG SOP)."
        elif "excite" in lbl or "why" in lbl or "motivation" in lbl:
            val = f"I'm excited about the {role} role at {company} because it offers the opportunity to work on high-impact products and user experiences. My background developing production-grade applications like Aaku AI travel companion app and QuensultingAI Voice Receptionist has given me strong domain skills in product development and analytics."
        elif "video" in lbl or "youtube" in lbl or "2 minute" in lbl:
            val = "Video link will be provided upon request"
        elif "name" in lbl and "file" not in lbl:
            val = profile.get("name", config.profile.full_name)
            
        if val and idx is not None:
            fallback_plan.append({
                "index": idx,
                "action": "fill",
                "label": f.get("label", ""),
                "value": val
            })

    # 2. Click Option Actions for radio_questions
    for rq in radio_questions:
        q_idx = rq.get("question_index")
        q_title = rq.get("question", "").lower()
        opts = rq.get("options", [])
        chosen_opt = ""
        
        if "graduat" in q_title or "batch" in q_title or "year" in q_title:
            for o in opts:
                if "2026" in o:
                    chosen_opt = o
                    break
        elif "qualification" in q_title or "degree" in q_title or "highest" in q_title:
            for o in opts:
                if "b.tech" in o.lower() or "btech" in o.lower() or "b.e" in o.lower():
                    chosen_opt = o
                    break
        elif "available" in q_title or "start" in q_title or "notice" in q_title:
            for o in opts:
                if "15" in o or "immediate" in o.lower() or "less than" in o.lower():
                    chosen_opt = o
                    break
        
        if not chosen_opt and opts:
            for o in opts:
                if "other" not in o.lower():
                    chosen_opt = o
                    break
            if not chosen_opt:
                chosen_opt = opts[0]
                
        if chosen_opt and q_idx is not None:
            fallback_plan.append({
                "question_index": q_idx,
                "action": "click_option",
                "label": rq.get("question", ""),
                "value": chosen_opt
            })

    log(f"Generated Deterministic Heuristic Plan: {len(fallback_plan)} actions!")
    return fallback_plan

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

log(f"Opening system Chrome for {url}...")

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
        log("Launched persistent Chrome context successfully.")
    except Exception as ex:
        log(f"Persistent profile failed ({ex}). Launching direct Chrome...")
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = browser.new_context()
        log("Launched non-persistent Chrome context.")
    
    page = context.pages[0] if context.pages else context.new_page()
    
    try:
        log(f"Navigating to {url}...")
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        current_title = page.title()
        current_url = page.url
        log(f"Page loaded. Title: '{current_title}', URL: {current_url}")

        # Check if page is currently Google Sign-In / Login wall
        if "sign-in" in current_title.lower() or "sign in" in current_title.lower() or "accounts.google.com" in current_url:
            log("Google Sign-In screen detected! Pre-filling email...")
            try:
                email_input = page.query_selector("input[type='email'], input[name='identifier']")
                if email_input and email_input.is_visible():
                    email_input.fill(profile.get("email", "2004.vimal@gmail.com"))
                    email_input.dispatch_event("input")
                    email_input.dispatch_event("change")
                    log("Email pre-filled on sign-in page.")
            except Exception as ex:
                log(f"Email pre-fill error: {ex}")

            log("Waiting for sign-in completion (up to 3 minutes)...")
            for i in range(90):
                time.sleep(2)
                try:
                    ct = page.title().lower()
                    cu = page.url
                except Exception:
                    continue
                if "sign-in" not in ct and "sign in" not in ct and "accounts.google.com" not in cu:
                    log(f"Sign-in complete after {i*2}s! New title: '{page.title()}'")
                    page.wait_for_timeout(3000)
                    break
            else:
                log("Sign-in wait timed out after 3 minutes!")

        # If job_data is empty, extract context from the actual page
        if not job_data.get("raw_text") and not job_data.get("company"):
            log("job_data is empty! Extracting job context from loaded page...")
            try:
                page_title = page.title()
                page_text = page.evaluate("() => document.body.innerText") or ""
                # Use first 3000 chars of page text as job context
                job_data = {
                    "company": page_title.split(" - ")[0].split(" | ")[0].strip() if " - " in page_title or " | " in page_title else page_title.strip(),
                    "role": "Internship / Role",
                    "raw_text": page_text[:3000]
                }
                log(f"Extracted from page: company='{job_data['company']}', raw_text_len={len(job_data['raw_text'])}")
            except Exception as ex:
                log(f"Page text extraction failed: {ex}")
                job_data = {"company": "Company", "role": "Role", "raw_text": ""}

        # Generate live real-time AI action plan on the actual form page
        log(f"=== GENERATING LIVE AI ACTION PLAN ===")
        log(f"Current page: '{page.title()}' at {page.url}")
        
        live_plan = inspect_and_generate_live_plan(page, job_data, profile)
        if live_plan:
            action_plan = live_plan
            log(f"Live AI plan generated: {len(action_plan)} actions!")
        else:
            log(f"WARNING: Live plan returned empty! Falling back to pre-computed plan ({len(action_plan)} actions).")
        
        # Execute LLM Action Plan
        all_inputs = page.query_selector_all("input:not([type='hidden']), textarea, select")
        log(f"=== EXECUTING {len(action_plan)} ACTIONS across {len(all_inputs)} elements ===")
        
        filled_count = 0
        for item_idx, item in enumerate(action_plan):
            action = item.get("action")
            label = item.get("label", "")
            val = item.get("value", "")
            idx = item.get("index")
            
            try:
                if action == "fill" and val:
                    filled = False
                    
                    # Strategy 1: Match by direct element index
                    if idx is not None and isinstance(idx, int) and 0 <= idx < len(all_inputs):
                        target_el = all_inputs[idx]
                        if target_el and target_el.is_visible():
                            _lbl_attr = (target_el.get_attribute("aria-label") or target_el.get_attribute("placeholder") or "").strip().lower()
                            if _lbl_attr in ["other response", "other"]:
                                log(f"  [SKIPPED fill idx={idx}] '{label}' target is an Other response input box.")
                            else:
                                target_el.fill(str(val))
                                target_el.dispatch_event("input")
                                target_el.dispatch_event("change")
                                target_el.dispatch_event("blur")
                                page.wait_for_timeout(300)
                                filled = True
                                filled_count += 1
                                log(f"  [FILLED idx={idx}] '{label[:40]}' => '{str(val)[:60]}...'")
                             
                    # Strategy 2: Container text matching
                    if not filled and label:
                        containers = page.query_selector_all("div[role='listitem'], div[jsmodel], div.geFormItem, fieldset, label")
                        for container in containers:
                            try:
                                c_text = container.evaluate("el => el.innerText") or ""
                            except Exception:
                                continue
                            if label.lower()[:30] in c_text.lower():
                                inp = container.query_selector("input:not([type='hidden']), textarea")
                                if inp and inp.is_visible():
                                    _lbl_attr = (inp.get_attribute("aria-label") or inp.get_attribute("placeholder") or "").strip().lower()
                                    if _lbl_attr in ["other response", "other"]:
                                        log(f"  [SKIPPED fill container] '{label}' target is an Other response input box.")
                                        break
                                    inp.fill(str(val))
                                    inp.dispatch_event("input")
                                    inp.dispatch_event("change")
                                    inp.dispatch_event("blur")
                                    page.wait_for_timeout(300)
                                    filled = True
                                    filled_count += 1
                                    log(f"  [FILLED container] '{label[:40]}' => '{str(val)[:60]}...'")
                                    break
                                    
                    # Strategy 3: Playwright get_by_label / get_by_placeholder
                    if not filled and label:
                        try:
                            el = page.get_by_label(label, exact=False).first
                            if not el or not el.is_visible():
                                el = page.get_by_placeholder(label, exact=False).first
                            if el and el.is_visible():
                                _lbl_attr = (el.get_attribute("aria-label") or el.get_attribute("placeholder") or "").strip().lower()
                                if _lbl_attr not in ["other response", "other"]:
                                    el.fill(str(val))
                                    el.dispatch_event("input")
                                    el.dispatch_event("change")
                                    el.dispatch_event("blur")
                                    page.wait_for_timeout(300)
                                    filled = True
                                    filled_count += 1
                                    log(f"  [FILLED playwright] '{label[:40]}' => '{str(val)[:60]}...'")
                        except Exception:
                            pass
                    
                    if not filled:
                        log(f"  [MISS] Could not find element for: '{label[:60]}'")

                elif action == "click_option" and val:
                    clicked = False
                    val_str = str(val).strip()
                    val_lower = val_str.lower()
                    
                    q_blocks_exec = page.query_selector_all("div[role='listitem']")
                    q_idx = item.get("question_index")
                    
                    # 1. Primary Locator: Try direct question_index container
                    target_qb = None
                    if q_idx is not None and isinstance(q_idx, int) and 0 <= q_idx < len(q_blocks_exec):
                        target_qb = q_blocks_exec[q_idx]
                    
                    # 2. Secondary Locator: Match heading or option text in q_blocks
                    if not target_qb:
                        for qb in q_blocks_exec:
                            try:
                                heading_text = qb.evaluate("""el => {
                                    const h = el.querySelector('div[role="heading"], .M7eF9, .hoP2b');
                                    return h ? h.innerText.replace('*','').trim() : '';
                                }""") or ""
                                block_text = qb.evaluate("el => el.innerText") or ""
                            except Exception:
                                heading_text = ""
                                block_text = ""
                            
                            if label and (label.lower()[:20] in heading_text.lower() or label.lower()[:20] in block_text.lower()):
                                target_qb = qb
                                break
                            elif val_lower in block_text.lower():
                                target_qb = qb
                                break
                    
                    candidate_qbs = [target_qb] if target_qb else q_blocks_exec
                    
                    for qb in candidate_qbs:
                        if not qb:
                            continue
                        try:
                            # Step A: Dropdown (listbox / combobox)
                            is_dropdown = qb.evaluate("""el => !!el.querySelector('div[role="listbox"], div[role="combobox"], .v8y8e, select')""")
                            
                            if is_dropdown:
                                qb.evaluate("""el => {
                                    const lb = el.querySelector('div[role="listbox"], div[role="combobox"], .v8y8e, select');
                                    if (lb) lb.click();
                                }""")
                                page.wait_for_timeout(400)
                                
                                opt_clicked = page.evaluate("""(targetVal) => {
                                    const options = document.querySelectorAll('div[role="option"], option, div[data-value], .exportOption');
                                    for (const o of options) {
                                        const dv = (o.getAttribute('data-value') || o.getAttribute('value') || '').trim();
                                        const txt = (o.innerText || o.textContent || '').trim();
                                        if (dv === targetVal || txt === targetVal || txt.toLowerCase() === targetVal.toLowerCase() || (dv && dv.toLowerCase() === targetVal.toLowerCase())) {
                                            o.click();
                                            return true;
                                        }
                                    }
                                    return false;
                                }""", val_str)
                                
                                if opt_clicked:
                                    page.wait_for_timeout(300)
                                    clicked = True
                                    filled_count += 1
                                    log(f"  [CLICKED dropdown option] '{label[:40]}' => '{val_str[:50]}'")
                                    break
                            
                            # Step B: Radios / Checkboxes
                            clicked_radio = qb.evaluate("""(el, targetVal) => {
                                const radios = el.querySelectorAll('div[role="radio"], div[role="checkbox"]');
                                for (const r of radios) {
                                    const dv = r.getAttribute('data-value');
                                    const rText = (r.innerText || r.textContent || '').trim().toLowerCase();
                                    const tValLower = targetVal.toLowerCase().trim();
                                    
                                    let match = false;
                                    if (dv === targetVal || (dv && dv.toLowerCase() === tValLower)) match = true;
                                    if (!match && rText && (rText === tValLower || rText.includes(tValLower) || tValLower.includes(rText))) match = true;
                                    
                                    if (match) {
                                        r.click();
                                        const inner = r.querySelector('span, div, .vdLWh, .docssharedWizToggleLabeledContainer');
                                        if (inner) inner.click();
                                        r.setAttribute('aria-checked', 'true');
                                        return true;
                                    }
                                }
                                
                                const labels = el.querySelectorAll('label, .docssharedWizToggleLabeledContainer, span');
                                for (const lbl of labels) {
                                    const lText = lbl.innerText ? lbl.innerText.trim().toLowerCase() : '';
                                    if (lText && (lText === targetVal.toLowerCase() || lText.includes(targetVal.toLowerCase()) || targetVal.toLowerCase().includes(lText))) {
                                        lbl.click();
                                        return true;
                                    }
                                }
                                return false;
                            }""", val_str)
                            
                            if clicked_radio:
                                page.wait_for_timeout(300)
                                clicked = True
                                filled_count += 1
                                log(f"  [CLICKED radio/checkbox] '{label[:40]}' => '{val_str[:50]}'")
                                break
                        except Exception as choice_ex:
                            log(f"  [Choice eval error] {choice_ex}")

                    # Step C: Global Fallback to Playwright force click
                    if not clicked:
                        try:
                            r_elem = page.get_by_role("radio", name=val_str, exact=False).first
                            if r_elem and r_elem.is_visible():
                                r_elem.click(force=True)
                                page.wait_for_timeout(200)
                                clicked = True
                                filled_count += 1
                                log(f"  [CLICKED get_by_role radio] '{label[:40]}' => '{val_str[:50]}'")
                            else:
                                elem = page.get_by_text(val_str, exact=True).first
                                if not elem or not elem.is_visible():
                                    elem = page.get_by_text(val_str, exact=False).first
                                if elem and elem.is_visible():
                                    elem.click(force=True)
                                    page.wait_for_timeout(200)
                                    clicked = True
                                    filled_count += 1
                                    log(f"  [CLICKED text-fallback force] '{label[:40]}' => '{val_str[:50]}'")
                        except Exception:
                            pass
                    
                    if not clicked:
                        log(f"  [MISS click_option] '{label[:60]}' => '{val_str[:50]}'")
            except Exception as e:
                log(f"  [Action Error] {label[:30]}: {e}")
                
        log(f"=== FILL COMPLETE: {filled_count}/{len(action_plan)} actions succeeded ===")
        
        # Fallback: Profile Auto-Filler for still-empty basic fields
        try:
            for el in page.query_selector_all("input:not([type='hidden']), textarea"):
                if not el.is_visible():
                    continue

                aria_lbl = (el.get_attribute("aria-label") or "").strip().lower()
                ph_lbl = (el.get_attribute("placeholder") or "").strip().lower()
                if aria_lbl in ["other response", "other"] or ph_lbl in ["other response", "other"]:
                    continue

                val_curr = ""
                try:
                    val_curr = el.input_value().strip()
                except Exception:
                    pass

                if val_curr:
                    continue

                label_text = (aria_lbl or ph_lbl or el.get_attribute("name") or el.get_attribute("id") or "").lower()
                try:
                    parent = el.evaluate_handle('el => el.closest("div[role=\\"listitem\\"], label, fieldset")')
                    if parent:
                        lbl_t = parent.evaluate("el => el.innerText")
                        if lbl_t:
                            label_text = (label_text + " " + lbl_t).lower()
                except Exception:
                    pass

                if "email" in label_text:
                    el.fill(profile["email"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "location" in label_text or "city" in label_text or "address" in label_text:
                    el.fill(profile.get("location", "Chennai, Tamil Nadu, India"))
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "first name" in label_text:
                    el.fill(profile["first_name"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "last name" in label_text:
                    el.fill(profile["last_name"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "name" in label_text and "company" not in label_text and "user" not in label_text and "file" not in label_text:
                    el.fill(profile["name"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "phone" in label_text or "mobile" in label_text or "contact" in label_text:
                    el.fill(profile["phone"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif ("resume" in label_text and ("link" in label_text or "url" in label_text or "drive" in label_text)) or "gdrive" in label_text:
                    el.fill(profile["resume_gdrive_url"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "linkedin" in label_text:
                    el.fill(profile["linkedin"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "stipend" in label_text or "salary" in label_text:
                    el.fill(profile.get("last_stipend", "20,000 / month"))
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "github" in label_text or "portfolio" in label_text or "website" in label_text:
                    el.fill(profile["github"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "college" in label_text or "university" in label_text or "institute" in label_text:
                    el.fill(profile["college"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "degree" in label_text or "branch" in label_text or "major" in label_text:
                    el.fill(profile["degree"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "gpa" in label_text or "cgpa" in label_text or "marks" in label_text:
                    el.fill(profile["gpa"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                elif "graduat" in label_text or "batch" in label_text or "year" in label_text:
                    el.fill(profile["grad_year"])
                    el.dispatch_event("input")
                    el.dispatch_event("change")
                        
            # File upload for Resume
            if pdf_path and os.path.exists(pdf_path):
                log(f"Attempting resume upload for pdf_path: {pdf_path}")
                uploaded = False
                file_inputs = page.query_selector_all("input[type='file']")
                if file_inputs:
                    try:
                        file_inputs[0].set_input_files(pdf_path)
                        page.wait_for_timeout(1000)
                        uploaded = True
                        log(f"Resume uploaded directly: {pdf_path}")
                    except Exception as ex:
                        log(f"Direct file upload error: {ex}")

                if not uploaded:
                    try:
                        add_file_btn = page.query_selector("div[role='button']:has-text('Add File'), button:has-text('Add File')")
                        if not add_file_btn:
                            add_file_btn = page.get_by_text("Add File", exact=False).first
                        if add_file_btn and add_file_btn.is_visible():
                            add_file_btn.click()
                            log("Clicked 'Add File' button. Waiting for file picker...")
                            page.wait_for_timeout(2500)

                            for frame in page.frames:
                                frame_inputs = frame.query_selector_all("input[type='file']")
                                if frame_inputs:
                                    frame_inputs[0].set_input_files(pdf_path)
                                    page.wait_for_timeout(1500)
                                    uploaded = True
                                    log(f"Resume uploaded in frame: {pdf_path}")
                                    break
                            
                            if not uploaded:
                                fi_after = page.query_selector_all("input[type='file']")
                                if fi_after:
                                    fi_after[0].set_input_files(pdf_path)
                                    page.wait_for_timeout(1000)
                                    uploaded = True
                                    log(f"Resume uploaded after Add File click: {pdf_path}")
                    except Exception as af_ex:
                        log(f"Add File button upload error: {af_ex}")
        except Exception as e:
            log(f"Fallback auto-fill error: {e}")

        log("Form auto-filled! Chrome window staying open for review & submit.")
        log(f"=== LOG FILE: {LOG_FILE} ===")
        time.sleep(600)
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        log(traceback.format_exc())
