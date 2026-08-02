import json
import sys
from playwright.sync_api import sync_playwright

if len(sys.argv) < 2:
    print(json.dumps({"error": "No URL provided"}))
    sys.exit(1)

url = sys.argv[1]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(2000)
        
        title = page.title()
        
        fields = []
        elements = page.query_selector_all("input:not([type='hidden']), textarea, select")
        for idx, el in enumerate(elements):
            t = el.get_attribute("type") or el.tag_name
            name = el.get_attribute("name") or ""
            label = el.get_attribute("aria-label") or el.get_attribute("placeholder") or el.get_attribute("id") or ""
            
            if not label:
                try:
                    parent = el.evaluate_handle("el => el.closest('div[role=\"listitem\"], label')")
                    if parent:
                        label_text = parent.evaluate("el => el.innerText")
                        if label_text:
                            label = label_text.split('\n')[0][:80]
                except Exception:
                    pass
                        
            fields.append({
                "index": idx,
                "type": t,
                "name": name,
                "label": label.strip(),
                "id": el.get_attribute("id") or ""
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

        print(json.dumps({
            "title": title,
            "url": url,
            "fields": fields,
            "radio_questions": radio_questions
        }))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
    finally:
        browser.close()
