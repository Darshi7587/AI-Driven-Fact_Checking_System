# VeritAI — AI Fact & Claim Verification Platform

<div align="center">
  <img src="https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?style=for-the-badge&logo=google&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/MongoDB-Atlas-47A248?style=for-the-badge&logo=mongodb&logoColor=white" />
</div>

---

## 🧠 What is VeritAI?

VeritAI is a **next-generation AI-powered fact verification platform** that uses a multi-agent pipeline to verify claims in real-time. It's built for journalists, researchers, students, and anyone who needs to fight misinformation.

## ✅ Core Features

| Feature | Description |
|---------|-------------|
| 🤖 Multi-Agent Pipeline | Orchestrated AI agents: Extract → Search → Verify → Report |
| 🔍 Smart Web Search | DuckDuckGo search with multi-query strategy |
| 🧠 Hallucination Detection | Identify AI-generated false information |
| ⏰ Temporal Fact Checker | Detect outdated claims |
| 🎯 Source Trust Scoring | Rate sources from gov/edu (95%) to social media (20%) |
| ⚡ Confidence Scores | Per-claim confidence with Chain-of-Thought reasoning |
| 📊 Interactive Reports | Pie charts, bar charts, radial accuracy score |
| 📄 PDF Export | Download full reports as PDF |
| 🔐 JWT Authentication | Secure login/signup with session |
| 📜 History Dashboard | Browse and manage past reports |

## 🏗️ Architecture

```
User Input (Text / URL)
    ↓
Orchestrator Agent
    ├─→ Claim Extractor (Gemini)
    ├─→ Query Generator (Gemini) 
    ├─→ Web Search (DuckDuckGo)
    ├─→ Evidence Scraper (BeautifulSoup)
    ├─→ Verification Agent (Gemini CoT)
    ├─→ Hallucination Detector
    └─→ Report Generator
    ↓
MongoDB (persist report)
    ↓
React Frontend (display)
```

## 🚀 Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- MongoDB (local or Atlas)
- Google Gemini API Key ([Get one free](https://aistudio.google.com/app/apikey))

### 1️⃣ Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Start the server
uvicorn main:app --reload --port 8000
```

### 2️⃣ Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

### 3️⃣ Open the App

Visit: [http://localhost:5173](http://localhost:5173)

---

## 🔑 Getting Your Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **"Create API key"**
3. Copy the key
4. Add to `backend/.env`: `GEMINI_API_KEY=your_key_here`

## 🔑 MongoDB Setup

**Option A: Local MongoDB**
- Install [MongoDB Community](https://www.mongodb.com/try/download/community)
- Leave `MONGODB_URL=mongodb://localhost:27017` in `.env`

**Option B: MongoDB Atlas (Free Cloud)**
1. Create account at [mongodb.com/atlas](https://mongodb.com/atlas)
2. Create a free cluster
3. Get connection string and update `.env`

---

## 🎨 UI Screenshots

### Landing Page
- Animated hero with floating orbs
- Live demo claims showcase
- Feature grid with glassmorphism cards

### Dashboard
- Stats overview (reports, claims, hallucinations)
- Radial accuracy chart
- Recent reports feed

### Verification Page
- Text / URL toggle input
- Real-time pipeline progress animation
- Example texts for quick demo

### Report Page
- Accuracy score with color-coded radial chart
- Claims breakdown pie chart
- Per-claim confidence bar chart
- Expandable claim cards with:
  - Status badge (True/False/Partial/Unverifiable/Conflicting)
  - Confidence ring
  - Chain-of-Thought reasoning
  - Evidence sources with trust scores
  - Search queries used

---

## 🤖 AI Pipeline Details

### Claim Extraction
Uses **Chain-of-Thought** prompting to extract atomic, verifiable facts:
- Filters out opinions and predictions
- Marks temporal claims (time-sensitive)
- Categorizes claims (science, politics, health, etc.)

### Query Generation  
For each claim, generates **3 strategic queries**:
1. Direct verification query
2. Counter-evidence / alternative perspective
3. Context/background query

### Verification Logic
**Chain-of-Thought 6-step reasoning**:
1. Read evidence carefully
2. Identify supporting/contradicting parts
3. Check source trustworthiness
4. Detect conflicting information
5. Assess temporal accuracy
6. Determine final verdict based ONLY on evidence

### Classification Labels
| Label | Meaning |
|-------|---------|
| ✅ TRUE | Multiple authoritative sources confirm |
| ❌ FALSE | Evidence clearly contradicts |
| ⚠️ PARTIALLY_TRUE | Some aspects confirmed, some not |
| ❓ UNVERIFIABLE | Insufficient evidence |
| 🔄 CONFLICTING | Sources directly contradict each other |

### Source Trust Scoring
| Domain Type | Trust Score |
|------------|------------|
| PubMed, WHO, NIH | 95-97% |
| Reuters, AP News | 95% |
| BBC, NPR, PBS | 88-92% |
| .gov domains | 85% |
| .edu domains | 82-85% |
| Wikipedia | 70% |
| Reddit, Twitter | 25-30% |

---

## 📁 Project Structure

```
fin3/
├── backend/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Environment config
│   ├── requirements.txt     # Python dependencies
│   ├── .env                 # Your API keys (not committed)
│   ├── auth/
│   │   ├── jwt_handler.py   # JWT token creation/decoding
│   │   └── password_handler.py  # BCrypt hashing
│   ├── routes/
│   │   ├── auth_routes.py   # /api/auth/*
│   │   ├── verification_routes.py  # /api/verify/*
│   │   └── history_routes.py  # /api/history/*
│   ├── agents/
│   │   ├── orchestrator.py  # Master pipeline coordinator
│   │   ├── claim_extractor.py  # Gemini claim extraction
│   │   ├── query_generator.py  # Smart query generation
│   │   ├── web_search_agent.py  # DuckDuckGo search
│   │   ├── verification_agent.py  # Chain-of-Thought verification
│   │   └── hallucination_detector.py  # Hallucination + temporal check
│   ├── services/
│   │   ├── gemini_service.py  # Google Gemini API wrapper
│   │   ├── search_service.py  # DuckDuckGo search service
│   │   └── scraper_service.py  # BeautifulSoup + trust scoring
│   └── models/
│       ├── user_model.py    # User Pydantic models
│       └── report_model.py  # Report/Claim Pydantic models
└── frontend/
    ├── src/
    │   ├── App.jsx           # Router + auth guards
    │   ├── index.css         # Global styles + Tailwind
    │   ├── pages/
    │   │   ├── Landing.jsx   # Public landing page
    │   │   ├── Login.jsx     # Login page
    │   │   ├── Signup.jsx    # Registration page
    │   │   ├── Dashboard.jsx # User dashboard
    │   │   ├── Verify.jsx    # Verification input page
    │   │   ├── Report.jsx    # Detailed report page
    │   │   └── History.jsx   # Report history
    │   ├── layouts/
    │   │   └── DashboardLayout.jsx  # Sidebar + mobile nav
    │   ├── context/
    │   │   └── AuthContext.jsx  # Auth state management
    │   └── services/
    │       └── api.js        # Axios API client
    └── package.json
```

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | React 18 + Vite | UI framework |
| Styling | Tailwind CSS | Utility CSS |
| Animations | Framer Motion | Smooth transitions |
| Charts | Recharts | Data visualization |
| Backend | FastAPI + Python | REST API |
| AI | Google Gemini 2.0 Flash | LLM reasoning |
| Search | DuckDuckGo Search | Free web search |
| Scraping | BeautifulSoup4 | Content extraction |
| Database | MongoDB + Motor | Async document storage |
| Auth | JWT + BCrypt | Secure authentication |
| PDF | jsPDF + html2canvas | Report export |

---

## 🎯 Evaluation Framework Coverage

### Accuracy (40 pts)
- ✅ Atomic claim extraction with CoT prompting
- ✅ Multi-query search for comprehensive evidence
- ✅ Evidence-only verification (no hallucination in reasoning)

### Aesthetics (30 pts)
- ✅ Real-time pipeline progress animation
- ✅ Interactive highlighted claims with expandable evidence
- ✅ Clean, modern SaaS-level design (ChatGPT/Vercel style)

### Innovation (30 pts)
- ✅ Multi-agent architecture with retry logic
- ✅ Conflicting evidence detection and labeling
- ✅ Chain-of-Thought + temporal fact validation
- ✅ Source trust scoring algorithm
- ✅ Hallucination detection

---

## 📝 License

MIT License — Built for educational/hackathon purposes.
