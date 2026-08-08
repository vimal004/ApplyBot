import os
import re
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Dict, Any, List, Tuple
from config import config
from tailorer import ResumeTailorer

class HREmailSender:
    """
    Automated HR Cold Email Sender & Gmail Draft / Preview Generator.
    Sends personalized emails with attached tailored PDF resume via Gmail SMTP,
    and constructs direct Gmail compose links for previewing before sending.
    """

    @staticmethod
    def extract_valid_emails(raw: str) -> List[str]:
        """Extract all valid email addresses from a potentially messy LLM-generated string."""
        return re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', raw)

    @staticmethod
    def generate_email_payload(job_data: Dict[str, Any], pdf_resume_path: str) -> Dict[str, Any]:
        company = job_data.get("company", "Company")
        role = job_data.get("role", "Software Engineer")
        hr_email_raw = job_data.get("apply_target", "")
        # Extract the first valid email for salutation / compose; keep raw for Gmail URL
        valid_emails = HREmailSender.extract_valid_emails(hr_email_raw)
        hr_email = valid_emails[0] if valid_emails else hr_email_raw
        
        subject_custom = job_data.get("subject_line", "")
        if subject_custom:
            subject = subject_custom.replace("<Full Name>", config.profile.full_name)\
                                    .replace("<Your Name>", config.profile.full_name)\
                                    .replace("<Project No>", "1")\
                                    .replace("<Your Fav Animal>", "Panther")
        else:
            subject = f"Application for {role} Position - Vimal Manoharan"
            
        body = ResumeTailorer.generate_hr_cover_letter(company, role, job_data.get("requirements", []), hr_email)
        
        # Add single clean signature block
        signature = (
            f"\n\nBest regards,\n"
            f"Vimal Manoharan\n"
            f"B.Tech Computer Science Engineering (CGPA 8.91/10.0) | SRM IST '26\n"
            f"Phone: {config.profile.phone}\n"
            f"LinkedIn: {config.profile.linkedin_url}\n"
            f"GitHub: {config.profile.github_url}"
        )
        full_body = body + signature

        # Gmail Compose URL — first email in To:, rest in CC: so the draft mirrors what SMTP sends
        valid_emails = HREmailSender.extract_valid_emails(hr_email_raw)
        gmail_to  = valid_emails[0] if valid_emails else hr_email_raw
        gmail_cc  = ', '.join(valid_emails[1:]) if len(valid_emails) > 1 else ''
        params = {
            "view": "cm",
            "fs": "1",
            "to": gmail_to,
            "su": subject,
            "body": full_body
        }
        if gmail_cc:
            params["cc"] = gmail_cc
        gmail_compose_url = f"https://mail.google.com/mail/?{urllib.parse.urlencode(params)}"

        return {
            "to_email": hr_email_raw,   # raw string (may contain multiple); send_email will parse
            "subject": subject,
            "body": full_body,
            "pdf_path": pdf_resume_path,
            "company": company,
            "role": role,
            "gmail_compose_url": gmail_compose_url
        }

    @staticmethod
    def send_email(email_payload: Dict[str, Any]) -> Tuple[bool, str]:
        sender_email = config.email.sender_email
        app_password = config.email.app_password

        if not app_password:
            return False, "Gmail App Password not configured in GMAIL_APP_PASSWORD env var. Use the Gmail Preview button to send manually."

        # Extract all valid email addresses from potentially messy LLM output
        to_email_raw = email_payload.get('to_email', '')
        recipients = HREmailSender.extract_valid_emails(to_email_raw)
        if not recipients:
            return False, f"Failed to send email: No valid recipient address found in '{to_email_raw}'."

        primary   = recipients[0]
        cc_list   = recipients[1:]   # any extras go to CC

        try:
            msg = MIMEMultipart()
            msg['From']    = sender_email
            msg['To']      = primary
            msg['Subject'] = email_payload['subject']
            if cc_list:
                msg['Cc'] = ', '.join(cc_list)

            msg.attach(MIMEText(email_payload['body'], 'plain'))

            pdf_path = email_payload.get('pdf_path')
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
                    msg.attach(part)

            all_recipients = [primary] + cc_list   # SMTP envelope must include CC addresses
            with smtplib.SMTP(config.email.smtp_server, config.email.smtp_port) as server:
                server.starttls()
                server.login(sender_email, app_password)
                server.sendmail(sender_email, all_recipients, msg.as_string())

            if cc_list:
                return True, f"✅ Email sent to {primary} (CC: {', '.join(cc_list)})!"
            return True, f"✅ Email sent to {primary}!"
        except Exception as e:
            return False, f"Failed to send email: {e}"
