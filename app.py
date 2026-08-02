import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram_bot import ApplyBotPipeline
from email_sender import HREmailSender
from config import config

PORT = 5050

class ApplyBotHTTPRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"[ApplyBot HTTP] {self.address_string()} - {args[0]}")

    def send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/" or path == "/index.html":
            html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
            if os.path.exists(html_path):
                with open(html_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "Template File Not Found")
                
        elif path == "/api/profile":
            profile_dict = {
                "full_name": config.profile.full_name,
                "first_name": config.profile.first_name,
                "last_name": config.profile.last_name,
                "email": config.profile.email,
                "phone": config.profile.phone,
                "university": config.profile.university,
                "degree": config.profile.degree,
                "gpa": config.profile.gpa,
                "graduation_year": str(config.profile.graduation_year),
                "linkedin": config.profile.linkedin_url,
                "github": config.profile.github_url,
                "portfolio": config.profile.portfolio_url,
                "resume_gdrive_url": config.profile.resume_gdrive_url,
                "location": config.profile.location,
                "experience_years": config.profile.experience_years,
                "notice_period": config.profile.notice_period,
                "expected_salary": config.profile.expected_salary
            }
            res_payload = json.dumps(profile_dict).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_payload)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(res_payload)
            
        elif path.startswith("/outputs/"):
            file_name = os.path.basename(path)
            file_path = os.path.join(config.output_dir, file_name)
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                if file_name.endswith(".pdf"):
                    self.send_header("Content-Type", "application/pdf")
                    self.send_header("Content-Disposition", f"inline; filename=\"{file_name}\"")
                else:
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "File Not Found")
        else:
            self.send_error(404, "Endpoint Not Found")

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/api/process":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                raw_text = data.get("raw_text", "")
                superfast_mode = data.get("superfast_mode", False)

                result = ApplyBotPipeline.process_referral(raw_text, superfast_mode)
                
                response_json = json.dumps(result).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_json)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(response_json)
            except Exception as e:
                err_msg = json.dumps({"error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_msg)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(err_msg)

        elif path == "/api/send_email":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                success, msg = HREmailSender.send_email(data)
                
                res_payload = json.dumps({"success": success, "message": msg}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_payload)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(res_payload)
            except Exception as e:
                err_msg = json.dumps({"success": False, "message": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_msg)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(err_msg)
        elif path == "/api/answer_question":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                q = data.get("question", "")
                c = data.get("company", "Company")
                r = data.get("role", "Role")
                
                from tailorer import ResumeTailorer
                ans = ResumeTailorer.answer_custom_question(q, c, r)
                
                res_payload = json.dumps({"answer": ans}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_payload)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(res_payload)
            except Exception as e:
                err_msg = json.dumps({"error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_msg)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(err_msg)
        elif path == "/api/autofill_form":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                from form_filler import JobFormAutoFiller
                executed, status_msg, details = JobFormAutoFiller.execute_auto_fill(data)
                
                res_payload = json.dumps({"success": executed, "message": status_msg}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_payload)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(res_payload)
            except Exception as e:
                err_msg = json.dumps({"success": False, "message": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err_msg)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(err_msg)
        else:
            self.send_error(404, "API Endpoint Not Found")

def run_server():
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, ApplyBotHTTPRequestHandler)
    print(f"============================================================")
    print(f"⚡ ApplyBot Dashboard Running at: http://localhost:{PORT}")
    print(f"============================================================")
    httpd.serve_forever()

if __name__ == "__main__":
    run_server()
