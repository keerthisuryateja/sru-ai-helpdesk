# SR University AI Voice Helpdesk & Campus Management System

An intelligent, full-stack Conversational AI Voice Assistant and Administrative Management Platform purpose-built for SR University. Features natural voice synthesis, dialogue-context RAG over SQLite relational campus data, real-time audio visualization, and a comprehensive Admin CRUD portal.

---

## System Architecture & Highlights

```
┌─────────────────────────────────────────────────────────────┐
│                    User Interfaces                         │
│  • React + Vite SPA (Modern Voice Orb, Chat, Drawer)        │
│  • Admin Relational Management UI (/admin)                  │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / REST / Audio Blobs
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI Backend (main.py)                │
│  • CORS & Static Asset Routing                              │
│  • Multi-Turn Dialogue Session Management                   │
│  • Dynamic LLM Provider Selection & API Key Configuration   │
└──────────────┬───────────────────────────────┬──────────────┘
               │                               │
┌──────────────▼─────────────┐   ┌─────────────▼──────────────┐
│   Multi-Table RAG (rag.py) │   │ Voice Pipeline (voice.py)  │
│  • Faculty Directory       │   │  • STT: SpeechRecognition  │
│  • Administrative Staff    │   │  • TTS Tier 1: Edge-TTS    │
│  • Student Clubs           │   │  • TTS Tier 2: pyttsx3     │
│  • University Portals      │   │  • TTS Tier 3: Kokoro ONNX │
└──────────────┬─────────────┘   └─────────────┬──────────────┘
               │                               │
┌──────────────▼─────────────┐   ┌─────────────▼──────────────┐
│ SQLite DB (helpdesk.db)    │   │ ONNX Models (models/)      │
│ 830+ Faculty, 230+ Admins  │   │ kokoro-v0_19.onnx (local)  │
└────────────────────────────┘   └────────────────────────────┘
```

- **Voice-Enabled Conversational Agent (`/`)**:
  - Interactive voice chat featuring real-time speech recognition (STT) and low-latency natural TTS.
  - Contextual dialogue awareness for intelligent follow-ups (e.g., *"Who is the HOD of CSE?"* followed by *"What is their cabin number?"*).
  - Source record citations with category badges (`Faculty`, `Administrative Personnel`, `Student Club`, `College Website`).
  - Interactive Voice Orb with audio waveform pulsing animations.
- **Campus Admin Management Portal (`/admin`)**:
  - Complete CRUD operations across all 4 university tables.
- **Live Faculty Timetable & Schedule Engine (`timetable_service.py`)**:
  - Real-time fetching from `https://timetable.sruniv.com/searchDueReportPublic?faculty={emp_id}&room=`.
  - Intelligently maps faculty names (e.g., *"Dr. Poongodi"*) to employee IDs (e.g., `1009`) or accepts direct numeric IDs.
  - Real-time period slot calculation across standard university class hours:
    - **Current location & class**: Tells the exact subject, room number, block, floor, and batch (or states if they are currently free).
    - **Availability**: Answers *"Is Dr. Poongodi free?"* with their current status and next upcoming class.
    - **Free slots calculation**: Lists all available, unscheduled periods for today or any specified day.
    - **Daily & Weekly Timetables**: Shows classes for any day or the complete weekly schedule.
  - High-performance in-memory caching with TTL to ensure rapid sub-second responses.
  - REST endpoint: `GET /api/timetable?faculty={emp_id_or_name}`.
  - UI integration: Chat responses render a *"View Live Timetable"* button, and Admin Faculty rows include direct timetable links.
- **Tri-Tier Voice Pipeline**:
  - **Tier 1 (Edge-TTS)**: Ultra-realistic Microsoft Edge neural voices (`en-US-AriaNeural`).
  - **Tier 2 (pyttsx3)**: Zero-latency offline Windows SAPI5 system fallback.
  - **Tier 3 (Kokoro ONNX)**: Local neural TTS using the 82M Kokoro ONNX model (`models/`).
- **Flexible LLM Provider Support**:
  - Seamless auto-switching between **Groq** (`llama-3.3-70b-versatile`), **Google Gemini** (`gemini-2.5-flash`), **OpenAI** (`gpt-4o-mini`), or the built-in deterministic local factual synthesizer.

---

## Clean Repository Structure

```text
├── data/                       # Normalized university datasets (JSON)
│   ├── club_coordinators.json  # Club administration & faculty in-charge
│   ├── clubs.json              # Student technical & non-technical clubs
│   ├── contact_directory.json  # Campus emergency & facility contact details
│   ├── dean_positions.json     # University deans & administrative chairs
│   ├── department_heads.json   # School heads, HODs, & associate deans
│   ├── faculty_contacts.json   # Faculty mobile numbers & employee IDs
│   ├── faculty_directory.json  # Comprehensive faculty names & departments
│   └── timetables.json         # Academic portals, schedules, & fees links
├── frontend/                   # React 18 + Vite modern web application
│   ├── dist/                   # Production build distribution bundle
│   ├── public/                 # Static assets (SRU logo, voice orb)
│   ├── src/                    # App.jsx, index.css, main.jsx
│   ├── package.json            # Node.js dependencies
│   ├── vite.config.js          # Vite config & API reverse proxy
│   └── README.md               # Frontend documentation
├── models/                     # Local ONNX weights & speech models
│   ├── kokoro-v0_19.onnx       # Kokoro ONNX model (82M parameters)
│   └── voices.bin              # Voice embeddings binary
├── static/                     # Standalone HTML/CSS/JS fallback & Admin UI
│   ├── admin.html              # Relational database CRUD management UI
│   ├── admin.js                # Table controllers, modals, & API calls
│   ├── app.js                  # Vanilla JS voice recorder & chat interface
│   ├── index.html              # Fallback conversational UI
│   ├── styles.css              # Theme tokens & styling
│   ├── sru_logo.png            # Official SR University logo
│   └── sru_ai_voice_assistant_orb.png # Voice assistant orb graphic
├── database.py                 # SQLAlchemy ORM models & SQLite connection
├── helpdesk.db                 # SQLite database file
├── import_real_data.py         # Ingestion script mapping data/ JSONs to SQLite
├── main.py                     # FastAPI REST server & static mount handlers
├── rag.py                      # Multi-table retrieval & prompt generation
├── requirements.txt            # Python backend dependencies
├── seed_data.py                # Database seeder utility
├── voice.py                    # Multi-engine TTS & STT processing
├── .env.example                # Sample environment variables template
└── README.md                   # System documentation
```

---

## Quickstart Guide

### 1. Prerequisites
- **Python**: 3.10 to 3.13
- **Node.js**: 18+ (for building or developing the frontend)
- Microphone & speakers/headphones for voice chat

### 2. Backend Setup
```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Configure environment (optional, for LLM API keys)
cp .env.example .env

# 3. Seed real university data into SQLite database
python import_real_data.py

# 4. Start the FastAPI backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### 3. Frontend Setup (Optional for Dev / Rebuild)
The production React build is pre-compiled into `frontend/dist/` and served automatically at `http://127.0.0.1:8000/`.
If you wish to modify the React frontend:
```bash
cd frontend
npm install
npm run dev     # Runs dev server on http://localhost:5173 with proxy to backend
npm run build   # Compiles production bundle to frontend/dist/
```

---

## University Datasets

The `data/` folder contains structured campus information extracted and normalized into clean JSON files:
- **`faculty_directory.json`** & **`faculty_contacts.json`**: 830+ faculty members mapped to their departments, employee IDs, and verified contact numbers.
- **`department_heads.json`** & **`dean_positions.json`**: Heads of Departments (CSE, ECE, Mechanical, Civil, Management, Sciences) and Deans of Academics, R&D, Student Affairs, etc.
- **`contact_directory.json`**: Emergency contacts, hostel wardens, health center, security, and transport desk.
- **`clubs.json`** & **`club_coordinators.json`**: 36+ technical and cultural clubs (RoboSRU, CodeChef, IEEE, GDG, Rotaract, Spark, Sports) with faculty in-charge.
- **`timetables.json`**: Direct URLs to academic calendar, SRAAP student portal, and fee payment portals.

Run `python import_real_data.py` at any time to re-ingest and verify database records.

---

## API Reference

### Conversational Chat Endpoints
| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/chat/text` | `POST` | Process text query, returns strictly factual RAG response, source records, and synthesized TTS audio base64 |
| `/api/chat/voice` | `POST` | Transcribes multipart audio recording via STT, evaluates query via RAG, returns transcribed query and TTS audio |
| `/api/config` | `GET` | Retrieve active LLM provider (`groq`, `gemini`, `openai`, `local`) and masked key status |
| `/api/config` | `POST` | Update Groq API key dynamically at runtime |

### Admin CRUD Endpoints
| Resource | Routes | Supported Methods |
| :--- | :--- | :--- |
| **Faculty** | `/api/faculty`, `/api/faculty/{emp_id}` | `GET`, `POST`, `PUT`, `DELETE` |
| **Administrative Personnel** | `/api/administrative`, `/api/administrative/{person_id}` | `GET`, `POST`, `PUT`, `DELETE` |
| **Student Clubs** | `/api/clubs`, `/api/clubs/{club_id}` | `GET`, `POST`, `PUT`, `DELETE` |
| **College Websites** | `/api/websites`, `/api/websites/{site_id}` | `GET`, `POST`, `PUT`, `DELETE` |

---

## Application URLs

- **Interactive Voice Chatbot**: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- **Admin Management Portal**: [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin)
- **FastAPI Interactive Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
