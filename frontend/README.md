# SR University AI Helpdesk - Frontend Application

A responsive, high-performance web interface built with **React 18** and **Vite** for interacting with the SR University Conversational AI Voice Assistant.

---

## Key Features

- **Interactive Voice Orb**:
  - Dynamic visualizer with glowing energy ring, rotational physics, and responsive pulse animations reflecting microphone listening and speaking states.
  - One-click microphone toggle for live speech recording and automatic streaming to the voice recognition backend.
- **Conversational Chat Stream**:
  - Real-time message streaming with user questions and assistant answers.
  - Distinct badge tags for data sources: `Faculty`, `Administrative Personnel`, `Student Club`, `College Website`.
  - Inline audio player with play/replay and speed controls.
- **Campus Quick Directory Drawer**:
  - Slide-out drawer allowing students and staff to quickly search across 830+ faculty members, department heads, and campus facilities without leaving the conversation.
- **Runtime LLM Configuration Modal**:
  - Securely input and configure Groq API keys directly from the UI without restarting servers.
- **Theme System (Dark & Light Mode)**:
  - Clean CSS custom property system (`--bg`, `--card`, `--primary`, `--text-main`, etc.) with persistent state saved in `localStorage`.
- **Fast Production Build**:
  - Minified bundle compiled to `dist/` and served directly by the FastAPI backend under `/`.

---

## Directory Structure

```text
frontend/
├── dist/                # Production distribution bundle
│   ├── assets/          # Bundled JS and CSS chunks
│   ├── index.html       # Entrypoint HTML
│   ├── sru_logo.png     # Brand asset
│   └── sru_ai_voice_assistant_orb.png # Assistant orb asset
├── public/              # Static public assets
│   ├── sru_logo.png
│   └── sru_ai_voice_assistant_orb.png
├── src/                 # Application source code
│   ├── App.jsx          # Main application component & state management
│   ├── App.css          # Layout & drawer styles
│   ├── index.css        # Global CSS variables, animations, and theme styles
│   └── main.jsx         # React DOM entrypoint
├── index.html           # HTML template with Google Fonts (Plus Jakarta Sans)
├── package.json         # Node dependencies & build scripts
└── vite.config.js       # Vite bundler configuration & backend API proxy
```

---

## Scripts

### Run Development Server
```bash
npm run dev
```
Starts the local development server at `http://localhost:5173`. API requests to `/api`, `/static`, and images are automatically reverse-proxied to the FastAPI backend running at `http://127.0.0.1:8000`.

### Build for Production
```bash
npm run build
```
Compiles and bundles the application into `frontend/dist/`. The FastAPI backend automatically serves this production build when visitors open `http://127.0.0.1:8000/`.

### Preview Production Build
```bash
npm run preview
```
Runs a local static server to preview the built `dist/` directory.
