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
