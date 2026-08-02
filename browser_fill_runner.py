import sys
import os
import time
import json
from playwright.sync_api import sync_playwright

if len(sys.argv) < 5:
    print("Error: Missing parameters")
    sys.exit(1)

url = sys.argv[1]
action_plan = json.loads(sys.argv[2])
pdf_path = sys.argv[3]
profile = json.loads(sys.argv[4])

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
        
        # 1. Execute LLM Action Plan
        for item in action_plan:
            action = item.get("action")
            label = item.get("label", "")
            val = item.get("value", "")
            
            try:
                if action == "fill" and val:
                    el = page.get_by_label(label, exact=False).first if label else None
                    if not el or not el.is_visible():
                        el = page.get_by_placeholder(label, exact=False).first if label else None
                    if el and el.is_visible():
                        el.fill(str(val))
                        page.wait_for_timeout(300)
                elif action == "click_option" and val:
                    elem = page.get_by_text(str(val), exact=False).first
                    if elem and elem.is_visible():
                        elem.click()
                        page.wait_for_timeout(300)
            except Exception:
                pass
                
        # 2. General Profile Auto-Filler Fallback
        try:
            for el in page.query_selector_all("input:not([type='hidden']), textarea"):
                if not el.is_visible():
                    continue
                label = (el.get_attribute("aria-label") or el.get_attribute("placeholder") or el.get_attribute("name") or el.get_attribute("id") or "").lower()
                
                if not label:
                    try:
                        parent = el.evaluate_handle("el => el.closest('div[role=\"listitem\"], label')")
                        if parent:
                            lbl_t = parent.evaluate("el => el.innerText")
                            if lbl_t: label = lbl_t.split('\n')[0].lower()
                    except Exception:
                        pass
                        
                val_curr = ""
                try:
                    tag_name = el.evaluate("el => el.tagName").lower()
                    if tag_name == "input":
                        val_curr = el.input_value()
                except Exception:
                    pass
                if not val_curr:
                    if "email" in label:
                        el.fill(profile["email"])
                        el.dispatch_event("input")
                    elif "first name" in label:
                        el.fill(profile["first_name"])
                        el.dispatch_event("input")
                    elif "last name" in label:
                        el.fill(profile["last_name"])
                        el.dispatch_event("input")
                    elif "name" in label and "company" not in label:
                        el.fill(profile["name"])
                        el.dispatch_event("input")
                    elif "phone" in label or "mobile" in label or "contact" in label:
                        el.fill(profile["phone"])
                        el.dispatch_event("input")
                    elif ("resume" in label and ("link" in label or "url" in label or "drive" in label)) or "gdrive" in label:
                        el.fill(profile["resume_gdrive_url"])
                        el.dispatch_event("input")
                    elif "linkedin" in label:
                        el.fill(profile["linkedin"])
                        el.dispatch_event("input")
                    elif "github" in label or "portfolio" in label or "website" in label:
                        el.fill(profile["github"])
                        el.dispatch_event("input")
                    elif "college" in label or "university" in label or "institute" in label:
                        el.fill(profile["college"])
                        el.dispatch_event("input")
                    elif "degree" in label or "branch" in label or "major" in label:
                        el.fill(profile["degree"])
                        el.dispatch_event("input")
                    elif "gpa" in label or "cgpa" in label or "marks" in label:
                        el.fill(profile["gpa"])
                        el.dispatch_event("input")
                    elif "graduat" in label or "batch" in label or "year" in label:
                        el.fill(profile["grad_year"])
                        el.dispatch_event("input")
                        
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
