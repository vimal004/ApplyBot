import os
import urllib.parse
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Dict, Any, Tuple
from config import config
from tailorer import ResumeTailorer

class HREmailSender:
    """
    Automated HR Cold Email Sender & Gmail Draft / Preview Generator.
    Sends personalized emails with attached tailored PDF resume via Gmail SMTP,
    and constructs direct Gmail compose links for previewing before sending.
    """

    @staticmethod
    def generate_email_payload(job_data: Dict[str, Any], pdf_resume_path: str) -> Dict[str, Any]:
        company = job_data.get("company", "Company")
        role = job_data.get("role", "Software Engineer")
        hr_email = job_data.get("apply_target", "")
        
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

        # Gmail Compose Web URL for instant previewing inside Gmail
        params = {
            "view": "cm",
            "fs": "1",
            "to": hr_email,
            "su": subject,
            "body": full_body
        }
        gmail_compose_url = f"https://mail.google.com/mail/?{urllib.parse.urlencode(params)}"

        return {
            "to_email": hr_email,
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

        try:
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = email_payload['to_email']
            msg['Subject'] = email_payload['subject']
            
            msg.attach(MIMEText(email_payload['body'], 'plain'))
            
            pdf_path = email_payload.get('pdf_path')
            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
                    msg.attach(part)
                    
            with smtplib.SMTP(config.email.smtp_server, config.email.smtp_port) as server:
                server.starttls()
                server.login(sender_email, app_password)
                server.send_message(msg)
                
            return True, f"Successfully sent cold email to HR at {email_payload['to_email']}!"
        except Exception as e:
            return False, f"Failed to send email: {e}"
