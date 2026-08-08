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
    notice_period: str = "Immediate"
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
            "description": "Production-grade AI voice receptionist agent designed to manage dental clinic phone operations. Solves high-concurrency booking bottlenecks and mid-call latency. Implements a Dual-Mode Scheduling Architecture: (1) Synchronous Live Check querying Google Sheets in real-time to compute and offer same-day alternative slots during active calls, and (2) Asynchronous Post-Call webhook tasks to offload heavy Google Sheets storage and SMTP operations to prevent webhook timeouts. Features structured dialog state transitions, interruption/correction handling, global emergency escalation nodes, webhook signature verification, and a retry-once fault tolerance policy."
        },
        {
            "name": "Siddha Shivalayas Healthcare Management System",
            "url": "https://github.com/vimal004/Siddha-Shivalayas-Freelance",
            "live_demo": "https://siddhashivalayas.vercel.app",
            "tech": "React 18, Node.js, Express.js, MongoDB Atlas (Mongoose), Material-UI 5, Vite, JWT Auth, Docker, jsPDF, docxtemplater",
            "description": "Full-stack ERP system built for a traditional Siddha medicine clinic to automate patient registry, inventory tracking, and billing. Implements a multi-tenant database switcher middleware to cleanly isolate demo sandbox databases from production clinic data. Features HSN/GST-compliant invoice generation (PDF/DOCX exports), SOLID-compliant real-time inventory auto-deduction logic preventing race conditions during concurrent checkouts, role-based access control (RBAC), and JWT auth with secure HTTP-only cookies. Deployed in Docker containers managed behind Nginx."
        },
        {
            "name": "Intel Unnati AI Adaptive Quiz Game",
            "url": "https://github.com/vimal004/Intel-Unnati-Gen-AI-Project",
            "live_demo": "https://intel-unnati-game-frontend.vercel.app/",
            "tech": "Next.js, TypeScript, TailwindCSS, Python, Flask, Streamlit, T5 Transformer, XGBoost, SVD, MongoDB",
            "description": "GenAI personalized learning platform developed under the Intel Unnati program. Addresses learning engagement gaps using three distinct AI/ML models: (1) Fine-tuned T5 LLM Transformer for on-demand dynamic question/distractor generation, (2) XGBoost regressor adjusting quiz difficulty dynamically based on user history, and (3) SVD collaborative filtering engine generating personalized topic recommendations. Implements Next.js App Router, global React state context, Streamlit analytical model testing playground, and a responsive Material 3 UI design."
        },
        {
            "name": "Wanderlust Travel Experience App",
            "url": "https://github.com/vimal004/Travel-App",
            "tech": "React Native, Expo SDK 55, React Navigation v7, Material 3 Design, Reanimated (60FPS), Async Storage",
            "description": "High-performance cross-platform mobile travel app. Built with feature-based modular architecture to decouple Auth, Destinations, and Bookmarks. Implements Material 3 design tokens, Google Sans typography, custom context theme providers (dark/light system overrides), and liquid 60FPS UI interactions powered by React Native Reanimated. Features layout transitions, persistent favorites caching, and shimmer loading states to reduce perceived layout load latency."
        },
        {
            "name": "ApplyBot Stealth Form & Resume Automation Engine",
            "url": "https://github.com/vimal004/ApplyBot",
            "tech": "Python, Playwright, Groq LLM API, Chrome Extension (Manifest v3), LaTeX Compiler",
            "description": " recruiting assistant automates browser job portal filling and resume optimization. Features Playwright DOM crawler that dynamically inspects application pages, parses job descriptions, and matches them to a master resume. Uses Groq LLM to rewrite LaTeX bullet points and reorder skills to optimize ATS scores, compiles them via a Tectonic LaTeX compiler engine on-the-fly, and autofills forms via a Manifest v3 Chrome Extension."
        },
        {
            "name": "Multithreaded AI Product Comparator (Intel Programme)",
            "url": "https://github.com/vimal004/Multithreaded-AI-Product-Comparator-Intel-Programme-Final-Project-",
            "tech": "Python, Multithreading, BeautifulSoup, Node.js, Express.js, MongoDB",
            "description": "E-commerce data analytics platform. Uses Python's ThreadPoolExecutor to run concurrent web scraping tasks across multiple retail domains, parsing pricing, specs, and reviews. Feeds aggregated data into an AI classification pipeline. Backend API built on Node.js/Express with MongoDB serving deduplicated results."
        },
        {
            "name": "Proactively Speaker Session Booking Backend",
            "url": "https://github.com/vimal004/Proactively-Backend-Freelance",
            "tech": "Node.js, Express.js, MongoDB, JWT Authentication, REST APIs",
            "description": "Freelance REST backend managing booking slots, scheduling conflicts, and client notifications for speaker events. Features custom validation middleware preventing double-booking, token authorization, and automated email notifications."
        },
        {
            "name": "Product Comparator Backend Server",
            "url": "https://github.com/vimal004/Product-Comparator-Backend-Server",
            "tech": "Node.js, Express.js, REST APIs, Web Scraping, MongoDB",
            "description": "Robust e-commerce catalog API server. Features scheduled cron jobs to scrape and sync product catalogs, compute price drops, and manage user alerts. Structured around repository design patterns and MongoDB aggregation pipelines."
        },
        {
            "name": "AQI Prediction & Analytics Regression Model",
            "url": "https://github.com/vimal004/AQI-Prediction-Regression-Model",
            "tech": "Python, Scikit-learn, Pandas, NumPy, Matplotlib, Seaborn",
            "description": "Predictive air quality index analysis pipeline. Performs exploratory data analysis, cleans feature outliers, handles multicollinearity, and trains multiple regression models (Linear, Random Forest) to forecast AQI based on particulate concentrations."
        },
        {
            "name": "Student Performance Analytics & Visualization System",
            "url": "https://github.com/vimal004/Student-Performance-Analysis-Visualization-Comparison-System-Using-Python-Matplotlib-and-MySQL",
            "tech": "Python, Matplotlib, MySQL, Data Visualization",
            "description": "Data comparison tool querying academic performance records from MySQL databases. Generates descriptive analytics charts, student ranking metrics, and distribution plots using Matplotlib."
        },
        {
            "name": "E-Shop Full-Stack E-Commerce Platform",
            "url": "https://github.com/vimal004/E-Shop-Frontend",
            "tech": "React.js, Node.js, Express.js, MongoDB, Redux Toolkit, TailwindCSS",
            "description": "MERN-stack e-commerce project with secure client-side state management using Redux Toolkit. Features product category browsing, checkout state routing, cart persistence, and admin inventory dashboards."
        },
        {
            "name": "TaskFlow Hintro Workspace Manager",
            "url": "https://github.com/vimal004/TaskFlow-Hintro",
            "tech": "React.js, JavaScript, TailwindCSS, REST APIs",
            "description": "Interactive kanban desk manager. Implements drag-and-drop task state transitions, categories filtering, and local storage persistence for agile workspace organization."
        },
        {
            "name": "Clootrack Technical Assignment",
            "url": "https://github.com/vimal004/Clootrack-Assignment",
            "tech": "Node.js, Express.js, React.js, REST APIs",
            "description": "Full-stack caching demo platform. Demonstrates API route caching on Express to reduce database lookup overhead, client state synchronization, and mock analytics reporting."
        },
        {
            "name": "Alcovia Technical Assignment",
            "url": "https://github.com/vimal004/Alcovia-Assignment",
            "tech": "React.js, JavaScript, Modern CSS UI",
            "description": "Responsive dashboard mockup implementing pixel-perfect design specifications, dynamic grids, and interactive data visualization charts."
        },
        {
            "name": "Personal Portfolio Web Application",
            "url": "https://github.com/vimal004/Portfolio_Website",
            "tech": "React.js, HTML5/CSS3, JavaScript, Vercel",
            "description": "Interactive developer portfolio displaying projects, technical skills, and resume details. Built with responsive layout frameworks and client contact integration."
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
