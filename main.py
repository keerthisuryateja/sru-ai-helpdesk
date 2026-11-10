import json
import logging
import os
import time
import hmac
import hashlib
import secrets
from typing import Optional, List, Dict
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (
    get_db, init_db,
    Faculty, AdministrativePersonnel, StudentClub, CollegeWebsite, ChatMessage, UniversityKnowledge
)
from seed_data import seed_database
from rag import generate_rag_response, get_active_llm_provider
from voice import speech_to_text, text_to_speech_base64


logger = logging.getLogger("main")
logging.basicConfig(level=logging.INFO)

# Initialize database schema and ensure default seed on startup
init_db()
try:
    seed_database(force=False)
except Exception as e:
    logger.warning(f"Seeding check on startup: {e}")

app = FastAPI(
    title="SR University Helpdesk AI",
    description="Conversational Voice Chatbot & University Admin Management UI",
    version="1.0.0"
)

# Security Response Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


# ============================================================================
# Admin Authentication, Brute-Force Rate Limiting & Token Verification
# ============================================================================

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "sru_super_secret_admin_token_signing_key_2026")
USER_SECRET_KEY = os.getenv("USER_SECRET_KEY", "sru_super_secret_user_token_signing_key_2026")
VOICE_SECRET_KEY = os.getenv("VOICE_SECRET_KEY", "sru_super_secret_voice_token_signing_key_2026")
security_bearer = HTTPBearer(auto_error=False)

TOKEN_MAX_AGE = 86400 * 30  # 30 days persistent session

# Track failed login attempts: client_ip -> list of timestamps
_failed_login_attempts: Dict[str, List[float]] = {}
_failed_voice_login_attempts: Dict[str, List[float]] = {}

def check_login_rate_limit(client_ip: str):
    now = time.time()
    attempts = _failed_login_attempts.get(client_ip, [])
    # Keep attempts within the last 10 minutes (600s)
    attempts = [t for t in attempts if now - t < 600]
    _failed_login_attempts[client_ip] = attempts
    if len(attempts) >= 5:
        oldest = attempts[0]
        retry_after = max(1, int(600 - (now - oldest)))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Locked out for {retry_after} seconds to prevent brute-force attacks."
        )

def record_failed_login(client_ip: str):
    now = time.time()
    attempts = _failed_login_attempts.get(client_ip, [])
    attempts.append(now)
    _failed_login_attempts[client_ip] = attempts

def check_voice_login_rate_limit(client_ip: str):
    now = time.time()
    attempts = _failed_voice_login_attempts.get(client_ip, [])
    attempts = [t for t in attempts if now - t < 600]
    _failed_voice_login_attempts[client_ip] = attempts
    if len(attempts) >= 5:
        oldest = attempts[0]
        retry_after = max(1, int(600 - (now - oldest)))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Locked out for {retry_after} seconds to prevent brute-force attacks."
        )

def record_failed_voice_login(client_ip: str):
    now = time.time()
    attempts = _failed_voice_login_attempts.get(client_ip, [])
    attempts.append(now)
    _failed_voice_login_attempts[client_ip] = attempts

def create_admin_token() -> str:
    """Generate a tamper-proof HMAC-SHA256 admin session token with timestamp."""
    ts = str(int(time.time()))
    sig = hmac.new(ADMIN_SECRET_KEY.encode(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"

def create_user_token() -> str:
    """Generate a tamper-proof HMAC-SHA256 user session token with timestamp."""
    ts = str(int(time.time()))
    sig = hmac.new(USER_SECRET_KEY.encode(), ts.encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{sig}"

def create_voice_token() -> str:
    return create_user_token()

def validate_token_string(token: str, secret_key: str) -> bool:
    if not token or "." not in token:
        return False
    try:
        parts = token.split(".", 1)
        if len(parts) != 2:
            return False
        ts_str, sig = parts
        ts = int(ts_str)
        now = time.time()
        if now - ts > TOKEN_MAX_AGE or now < ts - 60:
            return False
        expected_sig = hmac.new(secret_key.encode(), ts_str.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig, expected_sig)
    except Exception:
        return False

def verify_admin_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> bool:
    """Dependency that ensures the caller presents a valid, unexpired admin token."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required. Please log in with the administrator password."
        )
    token = credentials.credentials
    if not validate_token_string(token, ADMIN_SECRET_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired admin session token. Please log in again."
        )
    return True

def verify_voice_token(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)) -> bool:
    """Dependency that ensures caller has valid user or admin credentials."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to use voice assistant."
        )
    token = credentials.credentials
    if (
        not validate_token_string(token, USER_SECRET_KEY)
        and not validate_token_string(token, ADMIN_SECRET_KEY)
        and not validate_token_string(token, VOICE_SECRET_KEY)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token. Please log in again."
        )
    return True

class AdminLoginRequest(BaseModel):
    password: str

class VoiceLoginRequest(BaseModel):
    password: str

class UnifiedLoginRequest(BaseModel):
    password: str
    role: Optional[str] = None  # "admin" | "user" | None (auto-detect)

@app.post("/api/auth/login")
def unified_login(payload: UnifiedLoginRequest, request: Request):
    """Unified login for students/users and administrators."""
    client_ip = request.client.host if request.client else "unknown"
    check_login_rate_limit(client_ip)

    provided = payload.password.strip()
    admin_pwd = os.getenv("ADMIN_PASSWORD", "sru_admin_2026").strip()
    user_pwd = os.getenv("USER_PASSWORD", os.getenv("VOICE_PASSWORD", "sru_user_2026")).strip()

    if payload.role == "admin":
        if hmac.compare_digest(provided, admin_pwd):
            if client_ip in _failed_login_attempts:
                del _failed_login_attempts[client_ip]
            return {
                "status": "success",
                "role": "admin",
                "token": create_admin_token(),
                "expires_in": TOKEN_MAX_AGE,
                "message": "Administrator login successful."
            }
        record_failed_login(client_ip)
        raise HTTPException(status_code=401, detail="Incorrect administrator password.")
    elif payload.role == "user":
        if hmac.compare_digest(provided, user_pwd):
            if client_ip in _failed_login_attempts:
                del _failed_login_attempts[client_ip]
            return {
                "status": "success",
                "role": "user",
                "token": create_user_token(),
                "expires_in": TOKEN_MAX_AGE,
                "message": "Student/User login successful."
            }
        record_failed_login(client_ip)
        raise HTTPException(status_code=401, detail="Incorrect user access password.")
    else:
        # Auto-detect role
        if hmac.compare_digest(provided, admin_pwd):
            if client_ip in _failed_login_attempts:
                del _failed_login_attempts[client_ip]
            return {
                "status": "success",
                "role": "admin",
                "token": create_admin_token(),
                "expires_in": TOKEN_MAX_AGE,
                "message": "Administrator login successful."
            }
        elif hmac.compare_digest(provided, user_pwd):
            if client_ip in _failed_login_attempts:
                del _failed_login_attempts[client_ip]
            return {
                "status": "success",
                "role": "user",
                "token": create_user_token(),
                "expires_in": TOKEN_MAX_AGE,
                "message": "Student/User login successful."
            }
        record_failed_login(client_ip)
        raise HTTPException(status_code=401, detail="Invalid password. Please check credentials.")

@app.get("/api/auth/verify")
def verify_unified_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)):
    """Check session token validity and return current role."""
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication token required.")
    token = credentials.credentials
    if validate_token_string(token, ADMIN_SECRET_KEY):
        return {"authenticated": True, "role": "admin", "message": "Admin session valid."}
    elif validate_token_string(token, USER_SECRET_KEY) or validate_token_string(token, VOICE_SECRET_KEY):
        return {"authenticated": True, "role": "user", "message": "User session valid."}
    raise HTTPException(status_code=401, detail="Session expired or invalid.")

@app.post("/api/admin/login")
def admin_login(payload: AdminLoginRequest, request: Request):
    return unified_login(UnifiedLoginRequest(password=payload.password, role="admin"), request)

@app.get("/api/admin/verify")
def verify_admin_status(is_admin: bool = Depends(verify_admin_token)):
    return {"authenticated": True, "role": "admin", "message": "Admin session valid."}

@app.post("/api/voice/login")
def voice_login(payload: VoiceLoginRequest, request: Request):
    return unified_login(UnifiedLoginRequest(password=payload.password, role="user"), request)

@app.get("/api/voice/verify")
def verify_voice_status(is_voice: bool = Depends(verify_voice_token)):
    return {"authenticated": True, "message": "Voice access valid."}


class ConfigPayload(BaseModel):
    groq_api_key: Optional[str] = None


@app.get("/api/config")
def get_config():
    groq_key = os.getenv("GROQ_API_KEY", "")
    masked_key = (groq_key[:4] + "..." + groq_key[-4:]) if len(groq_key) > 8 else ("Configured" if groq_key else "Not Set")
    return {
        "active_provider": get_active_llm_provider(),
        "has_groq": bool(groq_key and groq_key.strip()),
        "groq_masked": masked_key
    }


@app.post("/api/config")
def update_config(payload: ConfigPayload, is_admin: bool = Depends(verify_admin_token)):
    if payload.groq_api_key is not None:
        key = payload.groq_api_key.strip()
        os.environ["GROQ_API_KEY"] = key
        # Persist to .env
        try:
            env_path = os.path.join(os.path.dirname(__file__), ".env")
            lines = []
            if os.path.exists(env_path):
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if not line.startswith("GROQ_API_KEY="):
                            lines.append(line.rstrip())
            lines.insert(0, f"GROQ_API_KEY={key}")
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as e:
            logger.warning(f"Could not persist .env: {e}")

    return {
        "message": "Configuration updated successfully.",
        "active_provider": get_active_llm_provider()
    }



# ============================================================================
# Pydantic Schemas
# ============================================================================

class ChatTextRequest(BaseModel):
    query: str
    session_id: Optional[str] = "default-session"
    synthesize_voice: Optional[bool] = False


class FacultyCreate(BaseModel):
    emp_id: str
    name: str
    email: Optional[str] = "Not Available"
    cabin_id: Optional[str] = None


class FacultyUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    cabin_id: Optional[str] = None


class AdminPersonnelCreate(BaseModel):
    role: str
    name: str
    email: Optional[str] = "Not Available"
    cabin_room_number: str


class AdminPersonnelUpdate(BaseModel):
    role: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    cabin_room_number: Optional[str] = None


class KnowledgeCreate(BaseModel):
    category: str
    title: str
    content: str
    tags: Optional[str] = None


class KnowledgeUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None


class ClubCreate(BaseModel):
    club_name: str
    social_media_link: str


class ClubUpdate(BaseModel):
    club_name: Optional[str] = None
    social_media_link: Optional[str] = None


class WebsiteCreate(BaseModel):
    url: str
    purpose_tags: str


class WebsiteUpdate(BaseModel):
    url: Optional[str] = None
    purpose_tags: Optional[str] = None


# Mount React build assets if available

frontend_dist = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_dist) and os.path.exists(os.path.join(frontend_dist, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")


# ============================================================================
# Frontend Web Routes
# ============================================================================

@app.get("/", response_class=FileResponse)
def serve_home():
    react_index = os.path.join(os.path.dirname(__file__), "frontend", "dist", "index.html")
    if os.path.exists(react_index):
        return FileResponse(react_index)
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))


@app.get("/sru_logo.png")
def serve_logo():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "sru_logo.png"))


@app.get("/sru_ai_voice_assistant_orb.png")
def serve_orb():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "sru_ai_voice_assistant_orb.png"))


@app.get("/admin", response_class=FileResponse)
def serve_admin():
    react_index = os.path.join(os.path.dirname(__file__), "frontend", "dist", "index.html")
    if os.path.exists(react_index):
        return FileResponse(react_index)
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "admin.html"))


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "SR University Helpdesk AI"}


# ============================================================================
# Core Chatbot Endpoints (Text & Voice)
# ============================================================================

@app.post("/api/chat/text")
def chat_text(payload: ChatTextRequest, db: Session = Depends(get_db)):
    t_start = time.perf_counter()
    query = payload.query.strip()
    session_id = payload.session_id or "default-session"

    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")

    # 1. RAG search & strictly dry factual synthesis
    factual_response, matched_records, timings = generate_rag_response(query, session_id, db)

    # 2. Kokoro TTS synthesis
    audio_data_uri = ""
    tts_ms = 0.0
    if payload.synthesize_voice:
        t_tts_start = time.perf_counter()
        audio_data_uri = text_to_speech_base64(factual_response)
        tts_ms = (time.perf_counter() - t_tts_start) * 1000

    # 3. Store conversation turn in ChatMessage table
    user_msg = ChatMessage(session_id=session_id, role="user", content=query)
    bot_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=factual_response,
        matched_sources=json.dumps([r["data"] for r in matched_records])
    )
    db.add(user_msg)
    db.add(bot_msg)
    db.commit()

    total_ms = (time.perf_counter() - t_start) * 1000
    logger.info(
        f"[LATENCY BREAKDOWN] Query: '{query}' -> '{factual_response}' | "
        f"Search/RAG: {timings.get('rag_ms', 0):.1f}ms | "
        f"LLM: {timings.get('llm_ms', 0):.1f}ms | "
        f"TTS: {tts_ms:.1f}ms | "
        f"Total: {total_ms:.1f}ms"
    )

    return {
        "session_id": session_id,
        "query": query,
        "text": factual_response,
        "audio": audio_data_uri,
        "sources": matched_records,
        "timings": {
            "search_ms": round(timings.get("rag_ms", 0), 1),
            "llm_ms": round(timings.get("llm_ms", 0), 1),
            "tts_ms": round(tts_ms, 1),
            "total_ms": round(total_ms, 1)
        }
    }


@app.get("/api/tts")
def get_tts(
    text: str,
    token: Optional[str] = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
):
    raw_token = (credentials.credentials if credentials else None) or token
    if not raw_token or not (
        validate_token_string(raw_token, USER_SECRET_KEY)
        or validate_token_string(raw_token, ADMIN_SECRET_KEY)
        or validate_token_string(raw_token, VOICE_SECRET_KEY)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Voice authentication required for speech synthesis."
        )
    t_start = time.perf_counter()
    audio_uri = text_to_speech_base64(text)
    tts_ms = (time.perf_counter() - t_start) * 1000
    logger.info(f"[ASYNC TTS] Length: {len(text)} chars | TTS time: {tts_ms:.1f}ms")
    return {"audio": audio_uri, "tts_ms": round(tts_ms, 1)}



@app.post("/api/chat/audio")
async def chat_audio(
    audio: UploadFile = File(...),
    session_id: str = Form("default-session"),
    db: Session = Depends(get_db),
    _voice_auth: bool = Depends(verify_voice_token)
):
    try:
        audio_bytes = await audio.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read audio payload: {e}")

    # 1. Speech-To-Text
    in_filename = audio.filename or "audio.webm"
    transcribed_text = speech_to_text(audio_bytes, filename=in_filename)
    logger.info(f"[CHAT_AUDIO STT] Filename: {in_filename} ({len(audio_bytes)} bytes) -> Transcribed: '{transcribed_text}'")
    if not transcribed_text:
        transcribed_text = "(Audio captured, no clear speech detected)"
        factual_response = "No clear speech detected. Please speak clearly or type your query."
        return {
            "session_id": session_id,
            "query": transcribed_text,
            "text": factual_response,
            "audio": text_to_speech_base64(factual_response),
            "sources": []
        }

    # 2. RAG search & strictly factual synthesis
    factual_response, matched_records, timings = generate_rag_response(transcribed_text, session_id, db)

    # 3. Kokoro TTS synthesis
    audio_data_uri = text_to_speech_base64(factual_response)

    # 4. Save dialogue
    user_msg = ChatMessage(session_id=session_id, role="user", content=transcribed_text)
    bot_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=factual_response,
        matched_sources=json.dumps([r["data"] for r in matched_records])
    )
    db.add(user_msg)
    db.add(bot_msg)
    db.commit()

    return {
        "session_id": session_id,
        "query": transcribed_text,
        "text": factual_response,
        "audio": audio_data_uri,
        "sources": matched_records
    }


@app.get("/api/chat/history/{session_id}")
def get_chat_history(session_id: str, db: Session = Depends(get_db)):
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )
    return [m.to_dict() for m in messages]


@app.delete("/api/chat/history/{session_id}")
def clear_chat_history(session_id: str, db: Session = Depends(get_db)):
    db.query(ChatMessage).filter(ChatMessage.session_id == session_id).delete()
    db.commit()
    return {"message": f"History cleared for session {session_id}"}


@app.get("/api/chat/sessions")
def get_recent_sessions(db: Session = Depends(get_db)):
    sessions = (
        db.query(ChatMessage.session_id)
        .distinct()
        .limit(20)
        .all()
    )
    return [s[0] for s in sessions if s[0]]


# ============================================================================
# Admin CRUD: Faculty
# ============================================================================

@app.get("/api/faculty")
def get_all_faculty(db: Session = Depends(get_db)):
    faculty = db.query(Faculty).order_by(Faculty.emp_id.asc()).all()
    return [f.to_dict() for f in faculty]


@app.post("/api/faculty", status_code=status.HTTP_201_CREATED)
def create_faculty(item: FacultyCreate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    existing = db.query(Faculty).filter(Faculty.emp_id == item.emp_id).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Faculty with Employee ID '{item.emp_id}' already exists.")

    email_val = item.email.strip() if item.email and item.email.strip() else "Not Available"
    cabin = item.cabin_id.strip() if item.cabin_id and item.cabin_id.strip() else None
    new_faculty = Faculty(
        emp_id=item.emp_id.strip(),
        name=item.name.strip(),
        email=email_val,
        cabin_id=cabin
    )
    db.add(new_faculty)
    db.commit()
    db.refresh(new_faculty)
    return new_faculty.to_dict()


@app.put("/api/faculty/{emp_id}")
def update_faculty(emp_id: str, item: FacultyUpdate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    fac = db.query(Faculty).filter(Faculty.emp_id == emp_id).first()
    if not fac:
        raise HTTPException(status_code=404, detail="Faculty record not found.")

    data = item.model_dump(exclude_unset=True)
    if "name" in data and data["name"] is not None:
        fac.name = data["name"].strip()
    if "email" in data:
        email_val = (data["email"] or "").strip()
        fac.email = email_val if email_val else "Not Available"
    if "cabin_id" in data:
        cabin = (data["cabin_id"] or "").strip()
        fac.cabin_id = cabin if cabin else None

    db.commit()
    db.refresh(fac)
    return fac.to_dict()


@app.delete("/api/faculty/{emp_id}")
def delete_faculty(emp_id: str, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    clean_id = emp_id.strip()
    fac = db.query(Faculty).filter(
        (Faculty.emp_id == emp_id) | (Faculty.emp_id == clean_id)
    ).first()
    if not fac:
        fac = db.query(Faculty).filter(Faculty.emp_id.ilike(clean_id)).first()
    if not fac:
        raise HTTPException(status_code=404, detail=f"Faculty record '{emp_id}' not found.")
    db.delete(fac)
    db.commit()
    return {"message": f"Faculty record '{emp_id}' deleted successfully."}


# ============================================================================
# Admin CRUD: Administrative Personnel
# ============================================================================

@app.get("/api/administrative")
def get_all_administrative(db: Session = Depends(get_db)):
    records = db.query(AdministrativePersonnel).order_by(AdministrativePersonnel.id.asc()).all()
    return [r.to_dict() for r in records]


@app.post("/api/administrative", status_code=status.HTTP_201_CREATED)
def create_administrative(item: AdminPersonnelCreate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    new_admin = AdministrativePersonnel(
        role=item.role.strip(),
        name=item.name.strip(),
        email=(item.email or "Not Available").strip(),
        cabin_room_number=item.cabin_room_number.strip()
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)
    return new_admin.to_dict()


@app.put("/api/administrative/{record_id}")
def update_administrative(record_id: int, item: AdminPersonnelUpdate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    record = db.query(AdministrativePersonnel).filter(AdministrativePersonnel.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Administrative record not found.")

    if item.role is not None:
        record.role = item.role.strip()
    if item.name is not None:
        record.name = item.name.strip()
    if item.email is not None:
        record.email = item.email.strip()
    if item.cabin_room_number is not None:
        record.cabin_room_number = item.cabin_room_number.strip()

    db.commit()
    db.refresh(record)
    return record.to_dict()


@app.delete("/api/administrative/{record_id}")
def delete_administrative(record_id: int, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    record = db.query(AdministrativePersonnel).filter(AdministrativePersonnel.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Administrative record not found.")
    db.delete(record)
    db.commit()
    return {"message": f"Administrative record {record_id} deleted successfully."}


# ============================================================================
# Admin CRUD: Student Clubs
# ============================================================================

@app.get("/api/clubs")
def get_all_clubs(db: Session = Depends(get_db)):
    clubs = db.query(StudentClub).order_by(StudentClub.id.asc()).all()
    return [c.to_dict() for c in clubs]


@app.post("/api/clubs", status_code=status.HTTP_201_CREATED)
def create_club(item: ClubCreate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    new_club = StudentClub(
        club_name=item.club_name.strip(),
        social_media_link=item.social_media_link.strip()
    )
    db.add(new_club)
    db.commit()
    db.refresh(new_club)
    return new_club.to_dict()


@app.put("/api/clubs/{club_id}")
def update_club(club_id: int, item: ClubUpdate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    club = db.query(StudentClub).filter(StudentClub.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found.")

    if item.club_name is not None:
        club.club_name = item.club_name.strip()
    if item.social_media_link is not None:
        club.social_media_link = item.social_media_link.strip()

    db.commit()
    db.refresh(club)
    return club.to_dict()


@app.delete("/api/clubs/{club_id}")
def delete_club(club_id: int, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    club = db.query(StudentClub).filter(StudentClub.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Club not found.")
    db.delete(club)
    db.commit()
    return {"message": f"Club {club_id} deleted successfully."}


# ============================================================================
# Admin CRUD: College Websites
# ============================================================================

@app.get("/api/websites")
def get_all_websites(db: Session = Depends(get_db)):
    websites = db.query(CollegeWebsite).order_by(CollegeWebsite.id.asc()).all()
    return [w.to_dict() for w in websites]


@app.post("/api/websites", status_code=status.HTTP_201_CREATED)
def create_website(item: WebsiteCreate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    new_site = CollegeWebsite(
        url=item.url.strip(),
        purpose_tags=item.purpose_tags.strip()
    )
    db.add(new_site)
    db.commit()
    db.refresh(new_site)
    return new_site.to_dict()


@app.put("/api/websites/{site_id}")
def update_website(site_id: int, item: WebsiteUpdate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    site = db.query(CollegeWebsite).filter(CollegeWebsite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found.")

    if item.url is not None:
        site.url = item.url.strip()
    if item.purpose_tags is not None:
        site.purpose_tags = item.purpose_tags.strip()

    db.commit()
    db.refresh(site)
    return site.to_dict()


@app.delete("/api/websites/{site_id}")
def delete_website(site_id: int, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    site = db.query(CollegeWebsite).filter(CollegeWebsite.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Website not found.")
    db.delete(site)
    db.commit()
    return {"message": f"Website {site_id} deleted successfully."}


# ============================================================================
# Admin CRUD: University Knowledge (Fees, Rules, Permissions, Events, etc.)
# ============================================================================

@app.get("/api/knowledge")
def get_all_knowledge(category: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(UniversityKnowledge)
    if category and category.strip():
        query = query.filter(UniversityKnowledge.category == category.strip())
    records = query.order_by(UniversityKnowledge.id.asc()).all()
    return [r.to_dict() for r in records]


@app.post("/api/knowledge", status_code=status.HTTP_201_CREATED)
def create_knowledge(item: KnowledgeCreate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    new_record = UniversityKnowledge(
        category=item.category.strip(),
        title=item.title.strip(),
        content=item.content.strip(),
        tags=item.tags.strip() if item.tags else None
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record.to_dict()


@app.put("/api/knowledge/{record_id}")
def update_knowledge(record_id: int, item: KnowledgeUpdate, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    record = db.query(UniversityKnowledge).filter(UniversityKnowledge.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Knowledge record not found.")

    if item.category is not None:
        record.category = item.category.strip()
    if item.title is not None:
        record.title = item.title.strip()
    if item.content is not None:
        record.content = item.content.strip()
    if item.tags is not None:
        record.tags = item.tags.strip()

    db.commit()
    db.refresh(record)
    return record.to_dict()


@app.delete("/api/knowledge/{record_id}")
def delete_knowledge(record_id: int, db: Session = Depends(get_db), is_admin: bool = Depends(verify_admin_token)):
    record = db.query(UniversityKnowledge).filter(UniversityKnowledge.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Knowledge record not found.")
    db.delete(record)
    db.commit()
    return {"message": f"Knowledge record {record_id} deleted successfully."}


@app.post("/api/seed")
def reset_and_seed():
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Demo re-seeding has been disabled because real university data is now active in the database."
    )
