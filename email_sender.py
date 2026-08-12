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
        brevo_api_key = os.environ.get("BREVO_API_KEY", "")
        resend_api_key = os.environ.get("RESEND_API_KEY", "")
        sender_email = config.email.sender_email or "2004.vimal@gmail.com"
        sender_name = config.profile.full_name or "Vimal Manoharan"
        app_password = config.email.app_password

        # Extract all valid email addresses from potentially messy LLM output
        to_email_raw = email_payload.get('to_email', '')
        recipients = HREmailSender.extract_valid_emails(to_email_raw)
        if not recipients:
            return False, f"Failed to send email: No valid recipient address found in '{to_email_raw}'."

        primary   = recipients[0]
        cc_list   = recipients[1:]   # any extras go to CC

        pdf_path = email_payload.get('pdf_path')
        attachments_resend = []
        attachments_brevo = []
        if pdf_path and os.path.exists(pdf_path):
            import base64
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
                pdf_b64 = base64.b64encode(pdf_bytes).decode('utf-8')
                attachments_resend.append({
                    "filename": os.path.basename(pdf_path),
                    "content": pdf_b64
                })
                attachments_brevo.append({
                    "name": os.path.basename(pdf_path),
                    "content": pdf_b64
                })

        # Method 1: Brevo REST API (HTTPS port 443 — 300 free emails/day to ANY email on Render)
        if brevo_api_key:
            try:
                import urllib.request
                import json

                payload = {
                    "sender": {"name": sender_name, "email": sender_email},
                    "to": [{"email": primary}],
                    "replyTo": {"email": sender_email, "name": sender_name},
                    "subject": email_payload['subject'],
                    "textContent": email_payload['body']
                }
                if cc_list:
                    payload["cc"] = [{"email": addr} for addr in cc_list]
                if attachments_brevo:
                    payload["attachment"] = attachments_brevo

                req = urllib.request.Request(
                    "https://api.brevo.com/v3/smtp/email",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "api-key": brevo_api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status in (200, 201):
                        return True, f"✅ Email sent via Brevo API to {primary}!"
            except Exception as brevo_err:
                print(f"[EmailSender] Brevo API error: {brevo_err}. Retrying fallback APIs...")

        # Method 2: Resend REST API
        if resend_api_key:
            try:
                import urllib.request
                import json
                
                from_address = os.environ.get("RESEND_FROM_EMAIL", f"{sender_name} <onboarding@resend.dev>")
                
                payload = {
                    "from": from_address,
                    "to": [primary],
                    "reply_to": sender_email,
                    "subject": email_payload['subject'],
                    "text": email_payload['body']
                }
                if cc_list:
                    payload["cc"] = cc_list
                if attachments_resend:
                    payload["attachments"] = attachments_resend

                req = urllib.request.Request(
                    "https://api.resend.com/emails",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {resend_api_key}",
                        "Content-Type": "application/json"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=20) as resp:
                    if resp.status in (200, 201):
                        return True, f"✅ Email sent via Resend API to {primary}!"
            except Exception as resend_err:
                print(f"[EmailSender] Resend API error: {resend_err}. Retrying direct SMTP...")

        # Method 3: Direct Gmail SMTP (Fallback)
        if not app_password:
            return False, "Neither BREVO_API_KEY, RESEND_API_KEY, nor GMAIL_APP_PASSWORD is set. Set BREVO_API_KEY in Render environment."


        try:
            msg = MIMEMultipart()
            msg['From']    = sender_email
            msg['To']      = primary
            msg['Subject'] = email_payload['subject']
            if cc_list:
                msg['Cc'] = ', '.join(cc_list)

            msg.attach(MIMEText(email_payload['body'], 'plain'))

            if pdf_path and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(pdf_path))
                    part['Content-Disposition'] = f'attachment; filename="{os.path.basename(pdf_path)}"'
                    msg.attach(part)

            all_recipients = [primary] + cc_list
            import socket
            socket.setdefaulttimeout(20.0)

            sent_ok = False
            last_err = None

            try:
                with smtplib.SMTP_SSL(config.email.smtp_server, 465, timeout=20) as server:
                    server.login(sender_email, app_password)
                    server.sendmail(sender_email, all_recipients, msg.as_string())
                    sent_ok = True
            except Exception as err1:
                last_err = err1
                print(f"[EmailSender] Port 465 SSL failed ({err1}). Retrying with Port 587 STARTTLS...")

            if not sent_ok:
                try:
                    with smtplib.SMTP(config.email.smtp_server, config.email.smtp_port, timeout=20) as server:
                        server.starttls()
                        server.login(sender_email, app_password)
                        server.sendmail(sender_email, all_recipients, msg.as_string())
                        sent_ok = True
                except Exception as err2:
                    return False, f"Email sending failed via Resend and SMTP: ({last_err}), ({err2})"

            if cc_list:
                return True, f"✅ Email sent to {primary} (CC: {', '.join(cc_list)})!"
            return True, f"✅ Email sent to {primary}!"
        except Exception as e:
            return False, f"Failed to send email: {e}"

