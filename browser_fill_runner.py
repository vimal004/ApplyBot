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
    elements = page.query_selector_all("input:not([type='hidden']), textarea, select")
    log(f"Total input/textarea/select elements found: {len(elements)}")
    
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
                const aria = (el.getAttribute('aria-label') || '').trim();
                const ph = (el.getAttribute('placeholder') || '').trim();
                if (aria && !['your answer', 'option 1', 'short answer text', 'long answer text'].includes(aria.toLowerCase())) return aria;
                if (ph && !['your answer', 'option 1'].includes(ph.toLowerCase())) return ph;
                
                const container = el.closest('div[role="listitem"], div[jsmodel], fieldset, label');
                if (container) {
                    const heading = container.querySelector('div[role="heading"], legend, .M7eF9, .hoP2b, h1, h2, h3, h4');
                    if (heading && heading.innerText) {
                        const lines = heading.innerText.split("\\n").map(l => l.trim()).filter(l => l && l !== '*');
                        if (lines.length > 0) return lines[0];
                    }
                    const text = container.innerText || '';
                    const lines = text.split("\\n").map(l => l.trim()).filter(l => l && l !== '*');
                    if (lines.length > 0) return lines[0];
                }
                return aria || ph || el.name || el.id || '';
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
    q_blocks = page.query_selector_all("div[role='listitem']")
    log(f"div[role='listitem'] blocks found: {len(q_blocks)}")
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
                const heading = el.querySelector('div[role="heading"], .M7eF9, .hoP2b');
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
        f"Job Summary: {raw_text[:800]}\n\n"
        f"=== TEXT INPUT FIELDS (use action='fill', reference by 'index') ===\n{json.dumps(fields, indent=2)}\n\n"
        f"=== RADIO/CHOICE QUESTIONS (use action='click_option', reference by 'question_index') ===\n{json.dumps(radio_questions, indent=2)}\n\n"
        "Generate a JSON array with actions for ALL text fields AND ALL radio questions."
    )

    if not config.groq.api_key:
        log("ERROR: No Groq API key! Cannot call LLM.")
        return []

    models_to_try = [config.groq.model_name, "llama3-70b-8192", "mixtral-8x7b-32768", "gemma2-9b-it"]
    
    for model_candidate in models_to_try:
        log(f"Calling Groq API: model={model_candidate}, system_prompt_len={len(system_prompt)}, user_prompt_len={len(user_prompt)}")
        
        try:
            url_api = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.groq.api_key}",
                "User-Agent": "ApplyBot/1.0"
            }
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
            log(f"Request payload size: {len(req_data)} bytes")
            
            req = urllib.request.Request(url_api, data=req_data, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as response:
                res_bytes = response.read()
                res_data = json.loads(res_bytes.decode("utf-8"))
                
                llm_res = res_data["choices"][0]["message"]["content"].strip()
                log(f"LLM response received ({len(llm_res)} chars)")
                
                if "```" in llm_res:
                    parts = llm_res.split("```")
                    for p in parts:
                        if "[" in p and "]" in p:
                            llm_res = p.replace("json", "").strip()
                            break
                
                plan = json.loads(llm_res.strip())
                log(f"Parsed action plan: {len(plan)} actions")
                for a in plan:
                    log(f"  Plan: action={a.get('action')}, label='{str(a.get('label',''))[:40]}', value='{str(a.get('value',''))[:50]}'")
                return plan
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8") if e.fp else "N/A"
            log(f"Groq API HTTP Error {e.code} on model {model_candidate}: {error_body[:300]}")
            if e.code == 429:
                log("Rate limit hit! Sleeping 4 seconds before trying next model...")
                time.sleep(4)
                continue
        except Exception as e:
            log(f"Groq API Error on model {model_candidate}: {e}")
            continue

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
                    
                    # Strategy 1: Find question container and click matching radio/dropdown via JS
                    try:
                        q_blocks_exec = page.query_selector_all("div[role='listitem']")
                        for qb in q_blocks_exec:
                            try:
                                heading_text = qb.evaluate("""el => {
                                    const h = el.querySelector('div[role="heading"], .M7eF9, .hoP2b');
                                    return h ? h.innerText.replace('*','').trim() : '';
                                }""") or ""
                            except Exception:
                                heading_text = ""
                            
                            match_q = False
                            if label and heading_text and label.lower()[:20] in heading_text.lower():
                                match_q = True
                            elif label and not heading_text:
                                block_text = qb.evaluate("el => el.innerText") or ""
                                if label.lower()[:20] in block_text.lower():
                                    match_q = True

                            if match_q:
                                try:
                                    res = qb.evaluate("""(el, targetVal) => {
                                        // 1. Dropdown (listbox / combobox)
                                        const listbox = el.querySelector('div[role="listbox"], div[role="combobox"], .v8y8e, select');
                                        if (listbox) {
                                            listbox.click();
                                            return { isDropdown: true };
                                        }
                                        
                                        // 2. Radios / Checkboxes
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
                                                return { success: true };
                                            }
                                        }
                                        
                                        // 3. Fallback: match labeled container text
                                        const labels = el.querySelectorAll('label, .docssharedWizToggleLabeledContainer, span');
                                        for (const lbl of labels) {
                                            const lText = lbl.innerText ? lbl.innerText.trim().toLowerCase() : '';
                                            if (lText && (lText === targetVal.toLowerCase() || lText.includes(targetVal.toLowerCase()) || targetVal.toLowerCase().includes(lText))) {
                                                lbl.click();
                                                return { success: true };
                                            }
                                        }
                                        return { success: false };
                                    }""", str(val))
                                    
                                    if res and res.get("isDropdown"):
                                        page.wait_for_timeout(400)
                                        opt_clicked = page.evaluate("""(targetVal) => {
                                            const options = document.querySelectorAll('div[role="option"], option, div[data-value], .exportOption');
                                            for (const o of options) {
                                                const dv = (o.getAttribute('data-value') || o.getAttribute('value') || '').trim();
                                                const txt = (o.innerText || '').trim();
                                                if (dv === targetVal || txt === targetVal || txt.toLowerCase() === targetVal.toLowerCase() || (dv && dv.toLowerCase() === targetVal.toLowerCase())) {
                                                    o.click();
                                                    return true;
                                                }
                                            }
                                            return false;
                                        }""", str(val))
                                        if opt_clicked:
                                            page.wait_for_timeout(300)
                                            clicked = True
                                            filled_count += 1
                                            log(f"  [CLICKED dropdown option] '{label[:40]}' => '{str(val)[:50]}'")
                                            break
                                    elif res and res.get("success"):
                                        page.wait_for_timeout(300)
                                        clicked = True
                                        filled_count += 1
                                        log(f"  [CLICKED radio/checkbox] '{label[:40]}' => '{str(val)[:50]}'")
                                        break
                                except Exception as rex:
                                    log(f"  [Option JS error] {rex}")
                    except Exception as ex:
                        log(f"  [Choice container error] {ex}")
                    
                    # Strategy 2: Fallback to page-wide text click
                    if not clicked:
                        try:
                            elem = page.get_by_text(str(val), exact=True).first
                            if not elem or not elem.is_visible():
                                elem = page.get_by_text(str(val), exact=False).first
                            if elem and elem.is_visible():
                                elem.click()
                                page.wait_for_timeout(200)
                                clicked = True
                                filled_count += 1
                                log(f"  [CLICKED text-fallback] '{label[:40]}' => '{str(val)[:50]}'")
                        except Exception:
                            pass
                    
                    if not clicked:
                        log(f"  [MISS click_option] '{label[:60]}' => '{str(val)[:50]}'")
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
