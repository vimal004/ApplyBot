import os
import json
import subprocess
from typing import Dict, Any

class PlaywrightFormParser:
    """
    Automated Headless Form Inspector.
    Launches headless browser via runner script to extract live DOM fields.
    """

    @staticmethod
    def inspect_form_page(form_url: str, venv_python_path: str = None) -> Dict[str, Any]:
        python_bin = venv_python_path or os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
        runner_file = os.path.join(os.path.dirname(__file__), "form_inspector_runner.py")
        
        try:
            res = subprocess.run([python_bin, runner_file, form_url], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
            if res.returncode == 0 and res.stdout.strip():
                return json.loads(res.stdout.strip())
            else:
                print(f"[Form Inspector Warning] {res.stderr}")
                return {"error": res.stderr.strip() or "Failed to inspect form page."}
        except Exception as e:
            return {"error": str(e)}
