import os
from dataclasses import dataclass, field
from typing import List, Dict

# Zero-dependency .env file parser helper
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                # Strip spaces and optional surrounding quotes
                os.environ[key.strip()] = val.strip().strip("'\"")


@dataclass
class CandidateProfile:
    full_name: str = "Vimal Manoharan"
    first_name: str = "Vimal"
    last_name: str = "Manoharan"
    email: str = "2004.vimal@gmail.com"
    phone: str = "+91 76038 32537"
    raw_phone: str = "7603832537"
    location: str = "Chennai, Tamil Nadu, India"
    
    linkedin_url: str = "https://linkedin.com/in/vimalmanoharan04"
    github_url: str = "https://github.com/vimal004"
    portfolio_url: str = "https://github.com/vimal004"
    resume_gdrive_url: str = "https://drive.google.com/file/d/1ozzluGbJEgqQkFpfPu97VnXoLoDkE0Rw/view?usp=share_link"
    
    university: str = "SRM Institute of Science and Technology"
    degree: str = "Bachelor of Technology in Computer Science Engineering"
    gpa: str = "8.91 / 10.0"
    graduation_year: int = 2026
    batch_status: str = "2026 Batch"
    
    experience_years: str = "1+ years (Internships & Freelance)"
    notice_period: str = "Immediate / Student (Graduating 2026)"
    expected_salary: str = "As per industry standards / Negotiable"
    
    core_skills: List[str] = field(default_factory=lambda: [
        "Python", "JavaScript", "React.js", "React Native", "Expo", "Node.js", 
        "FastAPI", "Express.js", "Java", "C++", "SQL", "MongoDB", "LangChain", 
        "LangGraph", "RAG Pipelines", "AI Agents", "Docker", "AWS EC2", "Nginx", 
        "Chroma DB", "Tailwind CSS", "Scikit-learn", "Selenium"
    ])

@dataclass
class EmailConfig:
    sender_email: str = os.getenv("SENDER_EMAIL", "2004.vimal@gmail.com")
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    app_password: str = os.getenv("GMAIL_APP_PASSWORD", "")

@dataclass
class GroqConfig:
    api_key: str = os.getenv("GROQ_API_KEY", "")
    model_name: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    temperature: float = 0.7

@dataclass
class AppConfig:
    profile: CandidateProfile = field(default_factory=CandidateProfile)
    email: EmailConfig = field(default_factory=EmailConfig)
    groq: GroqConfig = field(default_factory=GroqConfig)
    
    # Auto-fill mode: 'MANUAL_REVIEW' or 'SUPERFAST_AUTO'
    auto_fill_mode: str = "MANUAL_REVIEW" 
    
    # Directory to store generated resumes
    output_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")

# Initialize default app config instance
config = AppConfig()
os.makedirs(config.output_dir, exist_ok=True)
