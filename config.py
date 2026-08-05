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
    
    key_projects: List[Dict[str, str]] = field(default_factory=lambda: [
        {
            "name": "QuensultingAI Voice Agent Receptionist",
            "url": "https://github.com/vimal004/QuensultingAI-Voice-Agent",
            "live_demo": "https://quensultingai-voice-agent.onrender.com",
            "tech": "RetellAI Conversational Flow, FastAPI (Python 3.12+), Google Sheets API, SMTP Email, Render, Pytest",
            "description": "Production-grade AI voice agent handling inbound clinic calls. Features real-time slot availability checking via RetellAI tools, progressive detail collection, emergency detection, human escalation, Google Sheets storage, and automated confirmation emails."
        },
        {
            "name": "Siddha Shivalayas Healthcare Management System",
            "url": "https://github.com/vimal004/Siddha-Shivalayas-Freelance",
            "live_demo": "https://siddhashivalayas.vercel.app",
            "tech": "React 18, Node.js, Express.js, MongoDB Atlas (Mongoose), Material-UI 5, Vite, JWT Auth, Docker, jsPDF, docxtemplater",
            "description": "Production full-stack healthcare web application built for a traditional Siddha medicine clinic. Manages patient records, HSN/GST-compliant inventory, billing with PDF/DOCX generation, purchase tracking, and role-based access control (Admin/Staff)."
        },
        {
            "name": "Intel Unnati AI Adaptive Quiz Game",
            "url": "https://github.com/vimal004/Intel-Unnati-Gen-AI-Project",
            "live_demo": "https://intel-unnati-game-frontend.vercel.app/",
            "tech": "Next.js, TypeScript, TailwindCSS, Python, Flask, Streamlit, T5 Transformer, XGBoost, SVD, MongoDB",
            "description": "Full-stack GenAI learning platform developed under Intel Unnati. Uses T5 LLM for dynamic quiz generation, XGBoost for real-time difficulty adjustment based on student performance, and SVD collaborative filtering for personalized topic recommendations."
        },
        {
            "name": "Wanderlust Travel Experience App",
            "url": "https://github.com/vimal004/Travel-App",
            "tech": "React Native, Expo SDK 55, React Navigation v7, Material 3 Design, Reanimated (60FPS), Async Storage",
            "description": "High-performance cross-platform mobile travel companion adhering to Material 3 design guidelines. Built with modular feature architecture, 60FPS fluid animations, dynamic dark mode, and persistent bookmarking."
        },
        {
            "name": "ApplyBot Stealth Form & Resume Automation Engine",
            "url": "https://github.com/vimal004/ApplyBot",
            "tech": "Python, Playwright, Groq LLM API, Chrome Extension (Manifest v3), LaTeX Compiler",
            "description": "Autonomous end-to-end recruitment assistant. Tailors LaTeX resumes dynamically to job descriptions and automates 1-click browser form filling using live Playwright DOM inspection and LLM reasoning."
        },
        {
            "name": "Multithreaded AI Product Comparator (Intel Programme)",
            "url": "https://github.com/vimal004/Multithreaded-AI-Product-Comparator-Intel-Programme-Final-Project-",
            "tech": "Python, Multithreading, BeautifulSoup, Node.js, Express.js, MongoDB",
            "description": "Final project for Intel Programme. Multithreaded web scraper and AI analysis pipeline aggregating price metrics and product specifications across major e-commerce platforms in parallel."
        },
        {
            "name": "Proactively Speaker Session Booking Backend",
            "url": "https://github.com/vimal004/Proactively-Backend-Freelance",
            "tech": "Node.js, Express.js, MongoDB, JWT Authentication, REST APIs",
            "description": "Freelance backend REST API service managing speaker bookings, slot scheduling, session validation, and client notifications."
        },
        {
            "name": "Product Comparator Backend Server",
            "url": "https://github.com/vimal004/Product-Comparator-Backend-Server",
            "tech": "Node.js, Express.js, REST APIs, Web Scraping, MongoDB",
            "description": "Scalable e-commerce backend service for aggregating product data across retailers, extracting pricing metrics, and computing real-time comparison analytics."
        },
        {
            "name": "AQI Prediction & Analytics Regression Model",
            "url": "https://github.com/vimal004/AQI-Prediction-Regression-Model",
            "tech": "Python, Scikit-learn, Pandas, NumPy, Matplotlib, Seaborn",
            "description": "Machine learning environmental data analysis and regression modeling predicting Air Quality Index (AQI) levels based on atmospheric pollutants."
        },
        {
            "name": "Student Performance Analytics & Visualization System",
            "url": "https://github.com/vimal004/Student-Performance-Analysis-Visualization-Comparison-System-Using-Python-Matplotlib-and-MySQL",
            "tech": "Python, Matplotlib, MySQL, Data Visualization",
            "description": "Academic analytics system querying student evaluation metrics from MySQL and generating comparative performance charts."
        },
        {
            "name": "E-Shop Full-Stack E-Commerce Platform",
            "url": "https://github.com/vimal004/E-Shop-Frontend",
            "tech": "React.js, Node.js, Express.js, MongoDB, Redux Toolkit, TailwindCSS",
            "description": "Modern full-stack e-commerce web application featuring user authentication, shopping cart management, product catalog filtering, and admin dashboard."
        },
        {
            "name": "TaskFlow Hintro Workspace Manager",
            "url": "https://github.com/vimal004/TaskFlow-Hintro",
            "tech": "React.js, JavaScript, TailwindCSS, REST APIs",
            "description": "Interactive kanban task management and workflow organization app built for productivity tracking."
        },
        {
            "name": "Clootrack Technical Assignment",
            "url": "https://github.com/vimal004/Clootrack-Assignment",
            "tech": "Node.js, Express.js, React.js, REST APIs",
            "description": "Full-stack web application assignment implementing data fetching, caching, and state management."
        },
        {
            "name": "Alcovia Technical Assignment",
            "url": "https://github.com/vimal004/Alcovia-Assignment",
            "tech": "React.js, JavaScript, Modern CSS UI",
            "description": "Responsive web dashboard implementation featuring clean UI components and dynamic state handling."
        },
        {
            "name": "Personal Portfolio Web Application",
            "url": "https://github.com/vimal004/Portfolio_Website",
            "tech": "React.js, HTML5/CSS3, JavaScript, Vercel",
            "description": "Personal developer portfolio highlighting skills, experience, project demos, and direct contact forms."
        }
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
