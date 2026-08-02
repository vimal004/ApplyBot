import os
import json
from typing import Dict, Any, Tuple
from config import config

class JobFormAutoFiller:
    """
    Job Portal & Google Form Auto-Filler.
    Maps standard candidate profile fields without wasting LLM tokens on speculative fake questions.
    Generates browser auto-fill scripts & bookmarklets for instant 1-click form completion.
    """

    @staticmethod
    def prepare_form_payload(job_data: Dict[str, Any], pdf_path: str) -> Dict[str, Any]:
        """
        Maps standard candidate fields and builds the browser auto-fill payload.
        """
        company = job_data.get("company", "Company")
        role = job_data.get("role", "Role")
        apply_url = job_data.get("apply_target", "")

        profile_data = {
            "full_name": config.profile.full_name,
            "first_name": config.profile.first_name,
            "last_name": config.profile.last_name,
            "email": config.profile.email,
            "phone": config.profile.phone,
            "raw_phone": config.profile.raw_phone,
            "university": config.profile.university,
            "degree": config.profile.degree,
            "cgpa": config.profile.gpa,
            "graduation_year": str(config.profile.graduation_year),
            "linkedin": config.profile.linkedin_url,
            "github": config.profile.github_url,
            "resume_gdrive_url": config.profile.resume_gdrive_url,
            "resume_path": pdf_path
        }

        # Build 1-click Browser Bookmarklet JavaScript code
        autofill_js = f"""
(function() {{
    const data = {json.dumps(profile_data)};
    console.log('[ApplyBot] Running auto-fill script for ' + data.full_name);

    function fillMatchingInputs() {{
        const inputs = document.querySelectorAll('input, textarea');
        inputs.forEach(el => {{
            const label = (el.getAttribute('aria-label') || el.name || el.placeholder || el.id || '').toLowerCase();
            const type = (el.type || '').toLowerCase();

            if (type === 'email' || label.includes('email')) {{
                el.value = data.email;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (type === 'tel' || label.includes('phone') || label.includes('mobile') || label.includes('contact')) {{
                el.value = data.phone;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (label.includes('full name') || (label.includes('name') && !label.includes('company') && !label.includes('first') && !label.includes('last'))) {{
                el.value = data.full_name;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (label.includes('first name')) {{
                el.value = data.first_name;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (label.includes('last name')) {{
                el.value = data.last_name;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (label.includes('linkedin')) {{
                el.value = data.linkedin;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (label.includes('github') || label.includes('portfolio') || label.includes('website')) {{
                el.value = data.github;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (label.includes('college') || label.includes('university') || label.includes('institute')) {{
                el.value = data.university;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (label.includes('degree') || label.includes('branch') || label.includes('major')) {{
                el.value = data.degree;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (label.includes('cgpa') || label.includes('gpa') || label.includes('percentage') || label.includes('marks')) {{
                el.value = data.cgpa;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }} else if (label.includes('graduat') || label.includes('batch') || label.includes('passing year')) {{
                el.value = data.graduation_year;
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            }}
        }});
    }}
    fillMatchingInputs();
    alert('⚡ ApplyBot: Form fields populated successfully!');
}})();
"""

        return {
            "apply_url": apply_url,
            "company": company,
            "role": role,
            "profile": profile_data,
            "autofill_js": autofill_js.strip(),
            "mode": config.auto_fill_mode
        }

    @staticmethod
    def execute_auto_fill(form_payload: Dict[str, Any], superfast_mode: bool = False) -> Tuple[bool, str, Dict[str, Any]]:
        from browser_auto_filler import AutomatedBrowserFiller
        form_url = form_payload.get("apply_url", "")
        pdf_path = form_payload.get("profile", {}).get("resume_path", "")
        
        if form_url:
            return AutomatedBrowserFiller.process_and_fill_form(form_payload, form_payload, pdf_path)
            
        return True, f"Form profile mapped for {form_payload.get('company')}.", form_payload
