import os
import sys
import json
import datetime
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

# Ensure python output logs are flushed immediately for Render / cloud logs
sys.stdout.reconfigure(line_buffering=True)
from telegram_bot import ApplyBotPipeline
from email_sender import HREmailSender
from config import config
from telegram_watcher import telegram_watcher, TelegramWatcher

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

PORT = int(os.environ.get("PORT", 5050))

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

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", "15")
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        if path == "/health" or path == "/ping":
            res_payload = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_payload)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(res_payload)
            return

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

        # ── Telegram Watcher Endpoints ──
        elif path == "/api/telegram/status":
            res_payload = json.dumps(telegram_watcher.status).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_payload)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(res_payload)

        elif path == "/api/telegram/queue":
            queue = TelegramWatcher.get_queue()
            res_payload = json.dumps(queue).encode("utf-8")
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
                length_hint = data.get("length_hint", "")
                
                from tailorer import ResumeTailorer
                ans = ResumeTailorer.answer_custom_question(q, c, r, jd_text=jd_text, page_context=page_context, length_hint=length_hint)
                
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
        elif path == "/api/telegram/fetch":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                self.rfile.read(content_length)  # consume body
            try:
                results = telegram_watcher.fetch_messages(limit=50)
                res_payload = json.dumps({
                    "success": True,
                    "fetched": len(results),
                    "message": f"Fetched {len(results)} new job postings"
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_payload)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(res_payload)
            except Exception as e:
                print(f"[ApplyBot API Error] /api/telegram/fetch failed: {e}")
                err = json.dumps({"success": False, "message": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(err)

        elif path == "/api/telegram/start":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                self.rfile.read(content_length)
            started = telegram_watcher.start_listener_thread()
            res_payload = json.dumps({
                "success": started,
                "status": telegram_watcher.status
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_payload)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(res_payload)

        elif path == "/api/telegram/stop":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                self.rfile.read(content_length)
            telegram_watcher.stop_listener()
            res_payload = json.dumps({
                "success": True,
                "status": telegram_watcher.status
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_payload)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(res_payload)

        elif path == "/api/telegram/settings":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                if "auto_send_email" in data:
                    telegram_watcher.set_auto_send_email(bool(data["auto_send_email"]))
                res_payload = json.dumps({
                    "success": True,
                    "status": telegram_watcher.status
                }).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_payload)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(res_payload)
            except Exception as e:
                err = json.dumps({"success": False, "message": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(err)

        elif path == "/api/telegram/queue/process":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                queue_id = data.get("id", "")
                raw_text = data.get("raw_text", "")
                superfast = data.get("superfast_mode", False)
                job_dict = data.get("job_dict", None)

                if raw_text or job_dict:
                    result = ApplyBotPipeline.process_referral(raw_text or "", superfast, job_dict=job_dict)
                    _log_application(result)
                    TelegramWatcher.remove_from_queue(queue_id)
                    response_json = json.dumps(result).encode("utf-8")
                    self.send_response(200)
                else:
                    response_json = json.dumps({"error": "No raw_text or job_dict provided"}).encode("utf-8")
                    self.send_response(400)

                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(response_json)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(response_json)
            except Exception as e:
                err = json.dumps({"error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(err)

        elif path == "/api/telegram/queue/skip":
            content_length = int(self.headers.get("Content-Length", 0))
            body_bytes = self.rfile.read(content_length)
            try:
                data = json.loads(body_bytes.decode("utf-8"))
                queue_id = data.get("id", "")
                removed = TelegramWatcher.remove_from_queue(queue_id)
                res_payload = json.dumps({"success": removed}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(res_payload)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(res_payload)
            except Exception as e:
                err = json.dumps({"success": False, "message": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(err)))
                self.send_cors_headers()
                self.end_headers()
                self.wfile.write(err)

        elif path == "/api/telegram/queue/clear":
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                self.rfile.read(content_length)
            TelegramWatcher.clear_queue()
            res_payload = json.dumps({"success": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(res_payload)))
            self.send_cors_headers()
            self.end_headers()
            self.wfile.write(res_payload)

        else:
            self.send_error(404, "API Endpoint Not Found")

def _free_port(port: int):
    import subprocess
    import time
    try:
        out = subprocess.check_output(["lsof", "-t", f"-i:{port}"]).decode().strip()
        if out:
            current_pid = os.getpid()
            killed_any = False
            for pid_str in out.split():
                try:
                    pid = int(pid_str)
                    if pid != current_pid:
                        print(f"[ApplyBot] Clearing process {pid} using port {port}...")
                        os.kill(pid, 9)
                        killed_any = True
                except Exception:
                    pass
            if killed_any:
                time.sleep(1.5)
    except Exception:
        pass

def run_server():
    import time
    _free_port(PORT)
    server_address = ("", PORT)
    HTTPServer.allow_reuse_address = True
    
    httpd = None
    for attempt in range(5):
        try:
            httpd = HTTPServer(server_address, ApplyBotHTTPRequestHandler)
            break
        except OSError as err:
            if err.errno == 48:
                print(f"[ApplyBot] Port {PORT} busy, retrying in 1s (attempt {attempt+1}/5)...")
                _free_port(PORT)
                time.sleep(1)
            else:
                raise err

    if not httpd:
        raise RuntimeError(f"Could not bind to port {PORT}")

    print(f"============================================================")
    print(f"⚡ ApplyBot Dashboard Running at: http://localhost:{PORT}")
    print(f"============================================================")

    # Run cleanup of old resumes/LaTeX (> 7 days) and old queue items (> 2 days) on startup
    try:
        telegram_watcher.clean_old_resumes_and_queue()
    except Exception as e:
        print(f"[Cleanup] Error during startup cleanup: {e}")

    # Auto-start Telegram watcher if credentials are configured
    if telegram_watcher.is_available:
        print(f"📡 Telegram auto-ingestion: Starting listener for '{config.telegram.group_name}'...")
        telegram_watcher.start_listener_thread()
    else:
        print(f"📡 Telegram auto-ingestion: Not configured (add TELEGRAM_API_ID/HASH to .env)")

    # Self-ping background thread: Pings public Render URL every 4 minutes to prevent Render free tier from sleeping
    def _keep_alive():
        import threading
        import time
        import urllib.request
        import os

        def _ping_loop():
            # Wait 60s after startup before first ping
            time.sleep(60)
            while True:
                url = f"http://127.0.0.1:{PORT}/health"
                try:
                    # On Render, ping external public URL so Render's ingress proxy detects activity.
                    # Localhost (127.0.0.1) pings bypass Render's proxy and do not reset Render's 15-min sleep timer.
                    external_url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("APP_URL")
                    if not external_url and os.getenv("RENDER"):
                        external_url = "https://automailer-vimal.onrender.com"

                    if external_url:
                        url = external_url.rstrip('/') + '/health'

                    req = urllib.request.Request(url, headers={"User-Agent": "ApplyBot-KeepAlive/1.0"})
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        _ = resp.read()
                        print(f"[KeepAlive] Self-ping successful to {url} at {datetime.datetime.now().strftime('%H:%M:%S')}")
                except Exception as e:
                    print(f"[KeepAlive Note] Self-ping status for {url}: {e}")
                # Ping every 4 minutes (240 seconds) -> safely below Render's 15-minute sleep threshold
                time.sleep(240)

        t = threading.Thread(target=_ping_loop, daemon=True, name="ApplyBotKeepAlive")
        t.start()

    _keep_alive()

    httpd.serve_forever()

if __name__ == "__main__":
    run_server()

