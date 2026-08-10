import os
import shutil
import subprocess
import urllib.request
import urllib.error
import json
from typing import Tuple
from config import config

class LaTeXCompiler:
    """
    LaTeX to PDF Resume Compiler.
    Compiles tailored .tex resumes into PDF using:
    1. Local tectonic / pdflatex / xelatex (if available)
    2. Online LaTeX compilation API (cloud fallback for Render / serverless)
    3. Static PDF fallback (last resort)
    """

    @staticmethod
    def _compile_online(tex_file_path: str, output_pdf_path: str) -> Tuple[bool, str]:
        """Compile LaTeX to PDF using the free LaTeX Online API (latexonline.cc)."""
        try:
            with open(tex_file_path, "r", encoding="utf-8") as f:
                tex_content = f.read()

            # Use latex.ytotech.com API (reliable, free, supports pdflatex)
            api_url = "https://latex.ytotech.com/builds/sync"
            payload = json.dumps({
                "compiler": "pdflatex",
                "resources": [
                    {
                        "main": True,
                        "content": tex_content
                    }
                ]
            }).encode("utf-8")

            req = urllib.request.Request(
                api_url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=90) as resp:
                if resp.status in (200, 201):
                    pdf_bytes = resp.read()
                    if len(pdf_bytes) > 100 and pdf_bytes[:5] == b"%PDF-":
                        os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
                        with open(output_pdf_path, "wb") as out:
                            out.write(pdf_bytes)
                        return True, "Successfully compiled tailored ATS PDF via cloud LaTeX API!"
                    else:
                        print(f"[Compiler Cloud] API returned non-PDF response ({len(pdf_bytes)} bytes)")
                        return False, "Cloud LaTeX API returned invalid PDF."
                else:
                    print(f"[Compiler Cloud] API returned status {resp.status}")
                    return False, f"Cloud LaTeX API error: HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")[:500]
            print(f"[Compiler Cloud] HTTP error {e.code}: {error_body}")
            return False, f"Cloud LaTeX API HTTP error: {e.code}"
        except Exception as e:
            print(f"[Compiler Cloud] Failed: {e}")
            return False, f"Cloud LaTeX compilation failed: {e}"

    @staticmethod
    def compile_tex_to_pdf(tex_file_path: str, output_pdf_path: str) -> Tuple[bool, str]:
        output_dir = os.path.dirname(output_pdf_path)
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(tex_file_path))[0]
        project_root = os.path.dirname(os.path.abspath(__file__))
        
        # 1. Check for Tectonic (Fast, modern, self-contained LaTeX engine)
        tectonic_bin = shutil.which("tectonic") or os.path.join(project_root, "tectonic") or "/opt/homebrew/bin/tectonic"
        if os.path.exists(tectonic_bin) or shutil.which("tectonic"):
            try:
                cmd_args = [tectonic_bin, "-o", output_dir, tex_file_path]
                res = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)

                # Check for output PDF
                generated_pdf = os.path.join(output_dir, f"{base_name}.pdf")
                if os.path.exists(generated_pdf):
                    if generated_pdf != output_pdf_path:
                        shutil.move(generated_pdf, output_pdf_path)
                    return True, "Successfully compiled tailored ATS PDF using Tectonic!"
                else:
                    print(f"[Compiler Error] Tectonic ran but produced no PDF.")
                    print(f"[Tectonic stderr]\n{res.stderr[-3000:]}")
            except Exception as e:
                print(f"[Compiler Warning] Tectonic compilation failed: {e}")

        # 2. Check for traditional pdflatex / xelatex
        for cmd in ["pdflatex", "xelatex", "lualatex"]:
            compiler_path = shutil.which(cmd) or f"/opt/homebrew/bin/{cmd}"
            if os.path.exists(compiler_path):
                try:
                    cmd_args = [compiler_path, "-interaction=nonstopmode", f"-output-directory={output_dir}", tex_file_path]
                    res = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=45)
                    generated_pdf = os.path.join(output_dir, f"{base_name}.pdf")
                    if os.path.exists(generated_pdf):
                        if generated_pdf != output_pdf_path:
                            shutil.move(generated_pdf, output_pdf_path)
                        return True, f"Successfully compiled tailored ATS PDF using {cmd}."
                    else:
                        print(f"[Compiler Error] {cmd} produced no PDF.\n{res.stderr[-1000:]}")
                except Exception as e:
                    print(f"[Compiler Warning] {cmd} execution failed: {e}")

        # 3. Cloud fallback: compile via online LaTeX API (ideal for Render / serverless)
        print("[Compiler] No local LaTeX found. Attempting cloud compilation...")
        success, msg = LaTeXCompiler._compile_online(tex_file_path, output_pdf_path)
        if success:
            return True, msg

        # 4. Last-resort: only copy static PDF if the caller was compiling the base main.tex
        # (never silently deliver the untailored static PDF when a tailored .tex was generated)
        is_base_tex = os.path.abspath(tex_file_path) == os.path.join(project_root, "main.tex")
        fallback_source = os.path.join(project_root, "Vimal_Resume.pdf")
        if is_base_tex and os.path.exists(fallback_source):
            shutil.copy(fallback_source, output_pdf_path)
            return True, "Prepared static PDF resume (LaTeX CLI compiler pending)."

        return False, "Failed to compile tailored LaTeX resume to PDF. No local compiler or cloud API available."
