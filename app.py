import os
import json
import datetime
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram_bot import ApplyBotPipeline
from email_sender import HREmailSender
from config import config

TRACKER_LOG_PATH = os.path.join(os.path.dirname(__file__), "outputs", "applications_log.json")

def _read_tracker():
    if not os.path.exists(TRACKER_LOG_PATH):
        return []
    try:
        with open(TRACKER_LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _write_tracker(entries):
    os.makedirs(os.path.dirname(TRACKER_LOG_PATH), exist_ok=True)
    with open(TRACKER_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

def _log_application(result):
    """Append a newly processed application into the tracker log."""
    try:
        job = result.get("job", {})
        action = result.get("action_result", {})
        entries = _read_tracker()
        pdf_path = result.get("pdf_path", "")
        pdf_filename = os.path.basename(pdf_path) if pdf_path else ""
        entry = {
            "id": datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "applied_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "company": job.get("company", "Unknown"),
            "role": job.get("role", "Unknown"),
            "location": job.get("location", ""),
            "salary": job.get("salary", ""),
            "apply_target": job.get("apply_target", ""),
            "apply_mode": action.get("type", "UNKNOWN"),
            "ats_score": result.get("ats_score", 0),
            "pdf_filename": pdf_filename,
            "status": "Applied" if action.get("sent") else "Draft",
            "notes": ""
        }
        entries.insert(0, entry)
        _write_tracker(entries)
    except Exception as e:
        print(f"[Tracker] Failed to log application: {e}")

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
        elif path == "/api/tracker":
            entries = _read_tracker()
            res_payload = json.dumps(entries).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_payload)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(res_payload)
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
                _log_application(result)   # persist to tracker
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
                jd_text = data.get("jd_text", "")
                page_context = data.get("page_context", "")
                
                from tailorer import ResumeTailorer
                ans = ResumeTailorer.answer_custom_question(q, c, r, jd_text=jd_text, page_context=page_context)
                
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
        elif path == "/api/tracker/update":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                entry_id = data.get("id")
                entries = _read_tracker()
                for e in entries:
                    if e["id"] == entry_id:
                        if "status" in data: e["status"] = data["status"]
                        if "notes"  in data: e["notes"]  = data["notes"]
                        break
                _write_tracker(entries)
                res_payload = json.dumps({"success": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_payload)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(res_payload)
            except Exception as e:
                err = json.dumps({"success": False, "message": str(e)}).encode("utf-8")
                self.send_response(500); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err))); self.send_cors_headers(); self.end_headers()
                self.wfile.write(err)
        elif path == "/api/tracker/delete":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                entry_id = data.get("id")
                entries = [e for e in _read_tracker() if e["id"] != entry_id]
                _write_tracker(entries)
                res_payload = json.dumps({"success": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_payload)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(res_payload)
            except Exception as e:
                err = json.dumps({"success": False, "message": str(e)}).encode("utf-8")
                self.send_response(500); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err))); self.send_cors_headers(); self.end_headers()
                self.wfile.write(err)
        elif path == "/api/tracker/add":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                company = data.get("company", "").strip() or "Unknown"
                role = data.get("role", "").strip() or "Unknown"
                location = data.get("location", "").strip()
                salary = data.get("salary", "").strip()
                apply_target = data.get("apply_target", "").strip()
                apply_mode = data.get("apply_mode", "MANUAL").strip()
                ats_score = int(data.get("ats_score", 0))
                status = data.get("status", "Applied").strip()
                notes = data.get("notes", "").strip()

                entries = _read_tracker()
                entry = {
                    "id": datetime.datetime.now().strftime("%Y%m%d%H%M%S%f"),
                    "applied_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "company": company,
                    "role": role,
                    "location": location,
                    "salary": salary,
                    "apply_target": apply_target,
                    "apply_mode": apply_mode,
                    "ats_score": ats_score,
                    "pdf_filename": "",
                    "status": status,
                    "notes": notes
                }
                entries.insert(0, entry)
                _write_tracker(entries)
                res_payload = json.dumps({"success": True, "entry": entry}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_payload)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(res_payload)
            except Exception as e:
                err = json.dumps({"success": False, "message": str(e)}).encode("utf-8")
                self.send_response(500); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err))); self.send_cors_headers(); self.end_headers()
                self.wfile.write(err)
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
