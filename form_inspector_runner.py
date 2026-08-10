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
        INPUT_SEL = "input:not([type='hidden']):not([type='radio']):not([type='checkbox']):not([type='submit']):not([type='button']):not([type='image']), textarea, select"
        elements = page.query_selector_all(INPUT_SEL)
        
        if not elements or not any(e.is_visible() for e in elements):
            for frame in page.frames:
                try:
                    f_elems = frame.query_selector_all(INPUT_SEL)
                    if f_elems and any(fe.is_visible() for fe in f_elems):
                        elements = f_elems
                        break
                except Exception:
                    pass

            if not elements or not any(e.is_visible() for e in elements):
                try:
                    apply_btn = page.query_selector("button:has-text('Apply'), a:has-text('Apply'), div[role='button']:has-text('Apply'), span:has-text('Apply'), button:has-text('Next'), span:has-text('Next')")
                    if apply_btn and apply_btn.is_visible():
                        apply_btn.click()
                        page.wait_for_timeout(2500)
                        elements = page.query_selector_all(INPUT_SEL)
                except Exception:
                    pass

        visible_count = 0
        for idx, el in enumerate(elements):
            if not el.is_visible():
                continue
            visible_count += 1
            
            # Skip "Other response" text inputs (belong to radio "Other:" options)
            _aria_lbl = (el.get_attribute("aria-label") or "").strip().lower()
            if _aria_lbl in ["other response", "other"]:
                continue
            
            # Skip inputs inside a radiogroup container
            try:
                inside_radio = el.evaluate("el => !!el.closest('div[role=\"radiogroup\"], div[role=\"group\"]')")
                if inside_radio:
                    continue
            except Exception:
                pass

            t = el.get_attribute("type") or el.evaluate("el => el.tagName")
            name = el.get_attribute("name") or ""
            aria_label = (el.get_attribute("aria-label") or "").strip()
            placeholder = (el.get_attribute("placeholder") or "").strip()
            id_attr = (el.get_attribute("id") or "").strip()
            try:
                lbl = el.evaluate("""el => {
                    const isGuid = (s) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test((s || '').trim());
                    const blockContainer = el.closest('.tally-block, div[data-block-id], div[role="listitem"], .form-group, .field, fieldset, label, div[class*="block"], div[class*="input"], div[class*="field"]');
                    if (blockContainer) {
                        const heading = blockContainer.querySelector('h1, h2, h3, h4, label, legend, div[role="heading"], .tally-text-block, .M7eF9, .hoP2b, .field-label, p');
                        if (heading && heading.innerText) {
                            const lines = heading.innerText.split("\\n").map(l => l.trim()).filter(l => l && l !== '*' && !isGuid(l));
                            if (lines.length > 0 && lines[0].length < 250 && !isGuid(lines[0])) return lines[0];
                        }
                    }
                    if (el.id) {
                        const lblEl = document.querySelector(`label[for="${el.id}"]`);
                        if (lblEl && lblEl.innerText && lblEl.innerText.trim() && !isGuid(lblEl.innerText.trim())) return lblEl.innerText.trim();
                    }
                    const aria = (el.getAttribute('aria-label') || '').trim();
                    if (aria && !['your answer', 'option 1', 'short answer text', 'long answer text', 'enter here'].includes(aria.toLowerCase()) && !isGuid(aria)) return aria;
                    const ph = (el.getAttribute('placeholder') || '').trim();
                    if (ph && !['your answer', 'option 1', 'enter here'].includes(ph.toLowerCase()) && !isGuid(ph)) return ph;
                    const name = (el.getAttribute('name') || el.getAttribute('id') || '').trim();
                    if (name && !isGuid(name)) return name;
                    return el.type || '';
                }""")
                label = lbl or f"Field_{idx}"
            except Exception:
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
                    return opts;
                }""")
            except Exception:
                options = []
            
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
