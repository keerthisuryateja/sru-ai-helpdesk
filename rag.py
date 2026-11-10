import os
import re
import json
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from dotenv import load_dotenv
from openai import OpenAI

from database import (
    SessionLocal, Faculty, AdministrativePersonnel, StudentClub, CollegeWebsite, ChatMessage, UniversityKnowledge
)

load_dotenv()
logger = logging.getLogger("rag")
logging.basicConfig(level=logging.INFO)

# Persistent OpenAI/Groq client singleton (reused across all requests with connection pooling)
_openai_client_instance: Optional[OpenAI] = None
_openai_client_key: Optional[str] = None

def get_groq_client(api_key: str) -> OpenAI:
    global _openai_client_instance, _openai_client_key
    if _openai_client_instance is None or _openai_client_key != api_key:
        _openai_client_instance = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=8.0,
            max_retries=1
        )
        _openai_client_key = api_key
    return _openai_client_instance

# ============================================================================
# AI-First Architecture:
#   1. User query → Fast database pre-retrieval
#   2. Groq AI answers directly using verified university facts
# ============================================================================

SYSTEM_PROMPT = """You are the official SR University AI assistant.
Location: SR University is located in Warangal, Telangana, India.
Leadership:
- Chancellor: Sri A. Varada Reddy
- Pro-Chancellor: Sri A. Madhukar Reddy
- Vice-Chancellor: Prof. Deepak Garg
- Pro Vice-Chancellor: Dr. V. Mahesh
- Registrar: Prof. P. Venkata Ramana Rao
Never state that the Governor of Tamil Nadu or any governor is the Chancellor.

Core rules:
1. Output concise, factual plain text. Use separate lines for lists. Do NOT use markdown (no asterisks, no hashes, no bold).
2. PRIVACY: Never output personal mobile or phone numbers. Provide only official email addresses, cabin numbers, or departments.
3. When asked about an individual faculty, staff, or officer (e.g. 'who is Dr. Sridhar Chintala', 'who is Dr. Ramesh'):
   State their full name, their designation/role (e.g. Director, AI & DL; Associate Professor; HOD; Dean), official email, and cabin/room location directly from the records.
4. When multiple faculty or staff match a query: list only their names (one per line). Do not dump emails/cabins unless specifically requested.
5. Academic Calendar link: https://sraap.in/acb_uploads/2026-27_1_BTECH_20260804.pdf. Never use expired links.
6. Upcoming holidays: In November 2026, the next holiday is Guru Nanak Jayanti on Tuesday, 24 November 2026, followed by Kisan Diwas (23 Dec) and Christmas (25 Dec).
7. If no record is found: answer "No matching university record found."
"""

def get_current_time_context() -> str:
    """Generate dynamic real-time clock context to keep LLM aware of the exact moment."""
    now = datetime.now()
    return f"Time Context: {now.strftime('%I:%M %p, %A, %d %B %Y')}. Lecture Hours: 09:30 AM - 05:30 PM."

GREETINGS = {"hi", "hello", "hey", "good morning", "good evening", "greetings", "howdy"}

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_university_database",
        "description": "Search the SR University database for faculty members, administrative staff, deans, HODs, student clubs, college websites, or university knowledge (fees, scholarships, attendance rules, permissions, gate pass, fests/events, hostel, placements, and campus facilities).",
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string",
                    "description": "The search query - person's name, department, role, fee rules, scholarship, attendance, gate pass, fest, hostel, placement, club, or portal."
                },
                "category": {
                    "type": "string",
                    "enum": ["all", "faculty", "administrative", "clubs", "websites", "knowledge", "fees", "rules", "permissions", "events", "hostel", "placements", "gamification", "ssm", "calendar", "holidays"],
                    "description": "Category to search. Use 'knowledge', 'calendar', or 'holidays' for academic calendar, holidays, fees, rules, permissions, events, hostel, placements, or SSM gamification. Use 'administrative' for offices, HODs, and deans. Use 'faculty' for professors. Use 'all' if unsure."
                }
            },
            "required": ["search_query"]
        }
    }
}


import unicodedata

def clean_plain_text(text: str) -> str:
    """Remove markdown formatting symbols while preserving clean line breaks and intact URLs."""
    if not text:
        return ""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("\u2011", "-").replace("\u2013", "-").replace("\u2014", "-")
    text = unicodedata.normalize("NFKD", text)

    # Protect URLs from having underscores/characters removed
    urls = []
    def _url_repl(m):
        urls.append(m.group(0))
        return f"@@@URLTOKEN{len(urls)-1}@@@"

    text = re.sub(r'https?://[^\s]+', _url_repl, text)

    # Remove markdown bold/italic/header symbols (without touching protected URLs)
    cleaned = re.sub(r"[\*#_`~\[\]]", "", text)

    # Restore URLs
    for idx, u in enumerate(urls):
        cleaned = cleaned.replace(f"@@@URLTOKEN{idx}@@@", u)

    # Normalize spaces per line while preserving line breaks
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in cleaned.splitlines()]
    result_lines = []
    blank = False
    for line in lines:
        if line:
            result_lines.append(line)
            blank = False
        elif not blank:
            result_lines.append("")
            blank = True
    return "\n".join(result_lines).strip()


STOP_WORDS = {
    "the", "and", "for", "with", "what", "where", "who", "which", "how", "can",
    "tell", "please", "about", "give", "university", "sru", "college", "any", "are",
    "room", "number", "cabin", "contact", "phone", "link", "website", "details", "info", "find",
    "is", "was", "will", "this", "that", "today", "date", "time", "day", "now", "get",
    "in", "of", "on", "at", "to", "by", "from", "as", "an", "a", "or", "if", "be", "do",
    "does", "did", "it", "its", "he", "she", "his", "her", "my", "me", "we", "us", "you",
    "your", "charge", "incharge", "know", "person", "staff", "sir", "madam",
    "dr", "prof", "professor", "mr", "mrs", "ms"
}


def extract_keywords(text: str) -> List[str]:
    """Tokenize and normalize text into meaningful query terms."""
    clean = re.sub(r"[^\w\s-]", " ", text.lower())
    tokens = [t.strip() for t in clean.split() if len(t.strip()) >= 2]
    return [t for t in tokens if t not in STOP_WORDS]


def _normalize_name_token(t: str) -> str:
    s = t.lower()
    s = s.replace("th", "t").replace("dh", "d").replace("ee", "i").replace("oo", "u").replace("sh", "s").replace("ch", "c")
    return s


def _get_word_variants(word: str) -> List[str]:
    """Get singular, plural, and base variants of a word for flexible matching."""
    w = word.lower().strip()
    variants = {w}
    if w.endswith("ies") and len(w) > 4:
        variants.add(w[:-3] + "y")
    elif w.endswith("es") and len(w) > 3:
        variants.add(w[:-2])
        variants.add(w[:-1])
    elif w.endswith("s") and len(w) > 2:
        variants.add(w[:-1])
    else:
        variants.add(w + "s")
        variants.add(w + "es")
    return list(variants)


def _contains_word(word: str, text: str) -> bool:
    """Check whole-word match using word boundary regex with basic stemming & transliteration."""
    variants = _get_word_variants(word)
    pattern = r"\b(" + "|".join(re.escape(v) for v in variants) + r")\b"
    if re.search(pattern, text, re.IGNORECASE):
        return True

    # Transliteration match (e.g. chinthala -> chintala)
    w_norm = _normalize_name_token(word)
    if len(w_norm) >= 4:
        tokens = re.findall(r'[a-zA-Z0-9]+', text.lower())
        for token in tokens:
            if len(token) >= 4 and _normalize_name_token(token) == w_norm:
                return True
            if len(word) >= 5 and len(token) >= 5:
                import difflib
                if difflib.SequenceMatcher(None, word.lower(), token).ratio() >= 0.84:
                    return True
    return False


ROLE_SYNONYMS = {
    "bus": ["bus", "buses", "transport", "transportation"],
    "buses": ["bus", "buses", "transport", "transportation"],
    "transport": ["bus", "buses", "transport", "transportation"],
    "transportation": ["bus", "buses", "transport", "transportation"],
    "fee": ["fee", "fees", "payment", "accounts", "dues"],
    "fees": ["fee", "fees", "payment", "accounts", "dues"],
    "payment": ["fee", "fees", "payment", "dues", "receipt", "receipts"],
    "receipt": ["fee", "fees", "payment", "dues", "receipt", "receipts"],
    "hostel": ["hostel", "hostels", "warden"],
    "hostels": ["hostel", "hostels", "warden"],
    "warden": ["hostel", "hostels", "warden"],
    "hod": ["head", "hod"],
    "head": ["head", "hod"],
    "cse": ["cse", "computer science"],
    "ece": ["ece", "electronics"],
    "eee": ["eee", "electrical"],
    "mech": ["mech", "mechanical"],
    "civil": ["civil"],
    "dean": ["dean", "deans"],
    "bonafide": ["bonafide", "certificate", "certificates"],
    "certificate": ["bonafide", "certificate", "certificates", "migration"],
    "certificates": ["bonafide", "certificate", "certificates", "migration"],
    "wifi": ["wi-fi", "wifi", "internet", "network"],
    "placement": ["placement", "placements", "career"],
    "placements": ["placement", "placements", "career"],
    "admission": ["admission", "admissions"],
    "admissions": ["admission", "admissions"],
    "sports": ["sport", "sports", "athletic"],
    "sport": ["sport", "sports", "athletic"],
    "library": ["library", "book", "books"],
    "ambulance": ["ambulance", "driver", "health", "emergency"],
    "health": ["health", "wellness", "medical", "doctor", "ambulance"],
    "scholarship": ["scholarship", "scholarships"],
    "ssm": ["ssm", "student success", "gamification", "coins", "alpha coins", "sigma coins", "penalty", "redeem", "leaderboard", "badges"],
    "coin": ["coin", "coins", "alpha", "sigma", "ssm", "redeem", "gamification"],
    "coins": ["coin", "coins", "alpha", "sigma", "ssm", "redeem", "gamification"],
    "alpha": ["alpha", "alpha coins", "ssm"],
    "sigma": ["sigma", "sigma coins", "ssm"],
    "penalty": ["penalty", "penalty coins", "deduction", "deductions", "ssm"],
    "redeem": ["redeem", "redemption", "ssm", "perks", "rewards"],
    "redemption": ["redeem", "redemption", "ssm", "perks", "rewards"],
    "leaderboard": ["leaderboard", "ranking", "rankings", "ssm"],
    "badge": ["badge", "badges", "levels", "titan", "luminary", "ace", "brave", "aspirant"],
    "badges": ["badge", "badges", "levels", "titan", "luminary", "ace", "brave", "aspirant"],
    "holiday": ["holiday", "holidays", "vacation", "break", "calendar"],
    "holidays": ["holiday", "holidays", "vacation", "break", "calendar"],
    "vacation": ["holiday", "holidays", "vacation", "break", "calendar"],
    "calendar": ["calendar", "academic calendar", "semester dates", "schedule", "exams"]
}


def search_database(query: str, db, category: str = "all") -> List[Dict[str, Any]]:
    """Search across university tables. Category can filter to specific table."""
    query_lower = query.lower().strip()
    keywords = extract_keywords(query)
    results = []

    # 1. Faculty
    if category in ("all", "faculty"):
        all_faculty = db.query(Faculty).all()
        for f in all_faculty:
            cabin_str = f", Cabin: {f.cabin_id}" if f.cabin_id else ""
            email_str = f", Email: {f.email}" if f.email and f.email != "Not Available" else ""
            text_corpus = f"{f.emp_id} {f.name} {f.email or ''} {f.cabin_id or ''}".lower()
            score = 0
            if query_lower in text_corpus:
                score += 20
            for kw in keywords:
                if _contains_word(kw, text_corpus):
                    score += 10
            if f.name.lower() in query_lower:
                score += 25
            if score > 0:
                results.append({
                    "type": "Faculty",
                    "id": f.emp_id,
                    "title": f.name,
                    "data": f.to_dict(),
                    "text": f"Faculty: {f.name}, Employee ID: {f.emp_id}{email_str}{cabin_str}",
                    "score": score
                })

    # 2. Administrative Personnel
    if category in ("all", "administrative"):
        all_admin = db.query(AdministrativePersonnel).all()
        for a in all_admin:
            email_str = f", Email: {a.email}" if a.email and a.email != "Not Available" else ""
            text_corpus = f"{a.role} {a.name} {a.email or ''} {a.cabin_room_number}".lower()
            score = 0
            if query_lower in text_corpus:
                score += 25
            for kw in keywords:
                if _contains_word(kw, text_corpus):
                    score += 10
                # Check role synonyms
                if kw in ROLE_SYNONYMS:
                    for syn in ROLE_SYNONYMS[kw]:
                        if _contains_word(syn, text_corpus):
                            score += 15
                            break
            if a.name.lower() in query_lower:
                score += 25
            if score > 0:
                results.append({
                    "type": "Administrative Personnel",
                    "id": a.id,
                    "title": f"{a.role} - {a.name}",
                    "data": a.to_dict(),
                    "text": f"Role: {a.role}, Name: {a.name}{email_str}, Cabin: {a.cabin_room_number}",
                    "score": score
                })

    # 3. Student Clubs
    if category in ("all", "clubs"):
        all_clubs = db.query(StudentClub).all()
        for c in all_clubs:
            text_corpus = f"{c.club_name} {c.social_media_link}".lower()
            score = 0
            if query_lower in text_corpus:
                score += 20
            for kw in keywords:
                if _contains_word(kw, text_corpus):
                    score += 10
            if score > 0:
                results.append({
                    "type": "Student Club",
                    "id": c.id,
                    "title": c.club_name,
                    "data": c.to_dict(),
                    "text": f"Club: {c.club_name}, Social Media Link: {c.social_media_link}",
                    "score": score
                })

    # 4. College Websites
    if category in ("all", "websites"):
        all_websites = db.query(CollegeWebsite).all()
        for w in all_websites:
            text_corpus = f"{w.url} {w.purpose_tags}".lower()
            score = 0
            if query_lower in text_corpus:
                score += 20
            for kw in keywords:
                if _contains_word(kw, text_corpus):
                    score += 10
            if score > 0:
                results.append({
                    "type": "College Website",
                    "id": w.id,
                    "title": w.url,
                    "data": w.to_dict(),
                    "text": f"URL: {w.url}, Purpose: {w.purpose_tags}",
                    "score": score
                })

    # 5. University Knowledge (Fees, Rules, Permissions, Events, Placements, Hostel, Facilities, SSM Gamification, Academic Calendar, Holidays)
    if category in ("all", "knowledge", "fees", "rules", "permissions", "events", "hostel", "placements", "gamification", "ssm", "coins", "calendar", "holidays"):
        all_knowledge = db.query(UniversityKnowledge).all()
        for k in all_knowledge:
            text_corpus = f"{k.title} {k.category} {k.content} {k.tags or ''}".lower()
            score = 0
            if query_lower in text_corpus:
                score += 35
            for kw in keywords:
                if _contains_word(kw, text_corpus):
                    score += 12
                if _contains_word(kw, k.title.lower()):
                    score += 20
                if _contains_word(kw, (k.tags or "").lower()):
                    score += 15
            if score > 0:
                results.append({
                    "type": "University Knowledge",
                    "id": k.id,
                    "title": k.title,
                    "data": k.to_dict(),
                    "text": f"[{k.category.upper()}] {k.title}:\n{k.content}",
                    "score": score
                })

    # If category filter yielded nothing, automatically expand to all tables
    if not results and category != "all":
        return search_database(query, db, category="all")

    results.sort(key=lambda x: x["score"], reverse=True)
    return results


def _build_conversation_messages(session_id: str, db) -> List[Dict[str, str]]:
    """Build conversation history as OpenAI-format messages for multi-turn context."""
    messages = []
    try:
        recent_msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(8)
            .all()
        )
        if recent_msgs:
            recent_msgs.reverse()
            for msg in recent_msgs:
                messages.append({
                    "role": msg.role,  # "user" or "assistant"
                    "content": msg.content
                })
    except Exception as e:
        logger.warning(f"Could not load conversation history: {e}")
    return messages


def get_active_llm_provider() -> str:
    if os.getenv("GROQ_API_KEY"):
        return "Groq AI (Online)"
    return "Built-in Engine"


def generate_rag_response(query: str, session_id: str, db) -> Tuple[str, List[Dict[str, Any]], Dict[str, float]]:
    """
    AI-First RAG Pipeline:
      1. Instant greeting check
      2. Send query to LLM with search_database tool
      3. LLM decides: answer directly OR call tool
      4. If tool called → search DB → send results back → LLM answers
      5. Fallback to keyword search if LLM unavailable
    Returns (text_response, matched_records, timing_dict)
    """
    timings = {}
    t_start = time.perf_counter()
    q_clean = query.strip()

    # Step 1: Instant greeting check (0ms, no LLM needed)
    if q_clean.lower().rstrip("!?.,") in GREETINGS:
        t_end = time.perf_counter()
        timings["rag_ms"] = 0.0
        timings["llm_ms"] = 0.0
        timings["total_ms"] = (t_end - t_start) * 1000
        return "Hi! I'm the SR University assistant. Ask me about faculty, offices, clubs, or campus links.", [], timings

    # Quick courtesies
    q_lower = q_clean.lower().rstrip("!?.,")
    if q_lower in {"thank you", "thanks", "thx"}:
        timings["rag_ms"] = 0.0
        timings["llm_ms"] = 0.0
        timings["total_ms"] = (time.perf_counter() - t_start) * 1000
        return "You're welcome!", [], timings
    if q_lower in {"bye", "goodbye", "see you"}:
        timings["rag_ms"] = 0.0
        timings["llm_ms"] = 0.0
        timings["total_ms"] = (time.perf_counter() - t_start) * 1000
        return "Goodbye! Feel free to ask anytime.", [], timings

    # Step 2: Try AI-first pipeline with Groq LLM
    groq_key = os.getenv("GROQ_API_KEY")
    t_llm_start = time.perf_counter()

    if groq_key and groq_key.strip():
        result = _ai_first_pipeline(q_clean, session_id, db, groq_key.strip(), timings, t_start)
        if result is not None:
            return result

    # Step 3: Fallback - when LLM is unavailable
    logger.info("[FALLBACK] LLM unavailable, using keyword fallback")

    t_search_start = time.perf_counter()
    matched_records = search_database(q_clean, db, category="all")
    t_search_end = time.perf_counter()
    timings["rag_ms"] = (t_search_end - t_search_start) * 1000
    timings["llm_ms"] = (t_search_start - t_llm_start) * 1000
    timings["total_ms"] = (t_search_end - t_start) * 1000

    if not matched_records or matched_records[0]["score"] < 15:
        return "No matching university record found.", [], timings

    # Format top result
    top = matched_records[0]["data"]
    if "role" in top:
        email_str = f", Email: {top['email']}" if top.get('email') and top.get('email') != 'Not Available' else ""
        ans = f"{top['role']}: {top['name']}{email_str}, Cabin: {top['cabin_room_number']}."
    elif "emp_id" in top:
        cabin_str = f", Cabin: {top['cabin_id']}" if top.get('cabin_id') else ""
        email_str = f", Email: {top['email']}" if top.get('email') and top.get('email') != 'Not Available' else ""
        ans = f"{top['name']} (ID: {top['emp_id']}){email_str}{cabin_str}."
    elif "content" in top and "title" in top:
        ans = f"{top['title']}:\n{top['content']}"
    elif "club_name" in top:
        ans = f"{top['club_name']}: {top['social_media_link']}."
    else:
        ans = f"{top['url']}."

    return clean_plain_text(ans), matched_records[:1], timings


def _ai_first_pipeline(
    query: str, session_id: str, db, api_key: str,
    timings: dict, t_start: float
) -> Optional[Tuple[str, List[Dict[str, Any]], Dict[str, float]]]:
    """
    AI-first pipeline using Groq LLM with function calling.
    The LLM decides whether to search the DB or answer directly.
    Returns None if all LLM attempts fail (caller should use fallback).
    """
    try:
        client = get_groq_client(api_key)
    except Exception as e:
        logger.warning(f"Failed to get OpenAI client: {e}")
        return None

    # Pre-retrieve relevant university records in parallel (<15ms)
    t_search_start = time.perf_counter()
    pre_records = search_database(query, db, category="all")
    t_search_end = time.perf_counter()
    timings["rag_ms"] = (t_search_end - t_search_start) * 1000

    # Build message history for multi-turn context
    conversation_history = _build_conversation_messages(session_id, db)

    # Construct messages: dynamic system (with real-time clock) + pre-retrieved facts + history + current query
    dynamic_prompt = f"{get_current_time_context()}\n{SYSTEM_PROMPT}"
    messages = [{"role": "system", "content": dynamic_prompt}]

    has_strong_match = bool(pre_records and pre_records[0].get("score", 0) >= 12)

    if pre_records:
        context_items = [f"- {r['text'][:350]}" for r in pre_records[:4]]
        instruction = "OFFICIAL UNIVERSITY DATABASE RECORDS (Verified facts for this query - answer directly using these records):\n" if has_strong_match else "POTENTIAL DATABASE MATCHES:\n"
        messages.append({
            "role": "system",
            "content": instruction + "\n".join(context_items)
        })

    # Add last few conversation turns for context
    messages.extend(conversation_history[-3:])
    messages.append({"role": "user", "content": query})

    # Try models in order of speed and reliability: Qwen first (ultra-fast, no 429), then 20b, then 120b
    for model_name in ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]:
        try:
            t_llm_start = time.perf_counter()

            create_kwargs = {
                "model": model_name,
                "messages": messages,
                "max_tokens": 300,
                "temperature": 0.0
            }
            if not has_strong_match:
                create_kwargs["tools"] = [SEARCH_TOOL]
                create_kwargs["tool_choice"] = "auto"

            # Step A: First LLM call - AI answers directly with pre-retrieved facts or calls search tool
            completion = client.chat.completions.create(**create_kwargs)

            response_msg = completion.choices[0].message

            # Case 1: LLM answered directly in one turn (Fast Path: ~0.8 - 2.0s)
            if not getattr(response_msg, "tool_calls", None):
                raw_ans = response_msg.content.strip() if response_msg.content else ""
                clean_ans = clean_plain_text(raw_ans)
                t_llm_end = time.perf_counter()
                timings["llm_ms"] = (t_llm_end - t_llm_start) * 1000
                timings["total_ms"] = (t_llm_end - t_start) * 1000
                logger.info(
                    f"[AI-FAST-DIRECT] Model: {model_name} | Pre-retrieved: {len(pre_records)} | "
                    f"RAG: {timings['rag_ms']:.0f}ms | LLM: {timings['llm_ms']:.0f}ms | "
                    f"Total: {timings['total_ms']:.0f}ms | Answer: '{clean_ans[:60]}'"
                )
                return clean_ans, pre_records[:3], timings

            # Case 2: LLM called a search tool
            tool_call = response_msg.tool_calls[0]
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)

            t_search_start = time.perf_counter()
            search_query = func_args.get("search_query", query)
            category = func_args.get("category", "all")
            logger.info(f"[AI-TOOL-CALL] DB search requested: query='{search_query}', category='{category}'")
            matched_records = search_database(search_query, db, category=category)
            if matched_records:
                results_text = "\n".join([f"- {r['text'][:350]}" for r in matched_records[:6]])
            else:
                results_text = "No matching records found in the university database."

            t_search_end = time.perf_counter()
            timings["rag_ms"] = (t_search_end - t_search_start) * 1000

            # Step C: Second LLM call - AI formulates answer from search results
            messages.append(response_msg)  # Add assistant's tool call message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": results_text
            })

            final_completion = client.chat.completions.create(
                model=model_name,
                messages=messages,
                max_tokens=450,
                temperature=0.0
            )

            raw_ans = final_completion.choices[0].message.content.strip()
            clean_ans = clean_plain_text(raw_ans)

            t_llm_end = time.perf_counter()
            timings["llm_ms"] = (t_llm_end - t_llm_start) * 1000 - timings["rag_ms"]
            timings["total_ms"] = (t_llm_end - t_start) * 1000

            logger.info(
                f"[AI-TOOL-RESULT] Model: {model_name} | Tool: {func_name} ('{search_query}', {len(matched_records)} results) | "
                f"RAG: {timings['rag_ms']:.0f}ms | LLM: {timings['llm_ms']:.0f}ms | "
                f"Total: {timings['total_ms']:.0f}ms | Answer: '{clean_ans[:60]}'"
            )

            return clean_ans, matched_records[:3], timings

        except Exception as e:
            logger.warning(f"AI pipeline with {model_name} failed: {e}")
            continue

    # All models failed
    logger.warning("[AI-PIPELINE] All Groq models failed, falling back to keyword search")
    return None
