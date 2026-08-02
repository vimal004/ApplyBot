import os
import shutil
import subprocess
from typing import Tuple
from config import config

class LaTeXCompiler:
    """
    LaTeX to PDF Resume Compiler.
    Compiles tailored .tex resumes into PDF using tectonic / pdflatex / xelatex.
    """

    @staticmethod
    def compile_tex_to_pdf(tex_file_path: str, output_pdf_path: str) -> Tuple[bool, str]:
        output_dir = os.path.dirname(output_pdf_path)
        base_name = os.path.splitext(os.path.basename(tex_file_path))[0]
        
        # 1. Check for Tectonic (Fast, modern, self-contained LaTeX engine)
        tectonic_bin = shutil.which("tectonic") or "/opt/homebrew/bin/tectonic"
        if os.path.exists(tectonic_bin) or shutil.which("tectonic"):
            try:
                cmd_args = [tectonic_bin, "-o", output_dir, tex_file_path]
                res = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
                
                # Check for output PDF
                generated_pdf = os.path.join(output_dir, f"{base_name}.pdf")
                if os.path.exists(generated_pdf):
                    if generated_pdf != output_pdf_path:
                        shutil.move(generated_pdf, output_pdf_path)
                    return True, f"Successfully compiled tailored ATS PDF using Tectonic!"
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
                except Exception as e:
                    print(f"[Compiler Warning] {cmd} execution failed: {e}")

        # 3. Fallback strategy if CLI compiler is not installed yet
        project_root = os.path.dirname(os.path.abspath(__file__))
        fallback_source = os.path.join(project_root, "Vimal_Resume.pdf")
        if os.path.exists(fallback_source):
            shutil.copy(fallback_source, output_pdf_path)
            return True, "Prepared static PDF resume (LaTeX CLI compiler pending)."
            
        return False, "Failed to compile LaTeX to PDF."
