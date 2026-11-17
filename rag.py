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
# Dynamic Calendar & Holiday Engine (Real-Time Calculation)
# ============================================================================

OFFICIAL_UNIVERSITY_HOLIDAYS = {
    "2026-08-15": "Independence Day",
    "2026-08-26": "Eid Miladun Nabi",
    "2026-08-28": "Raksha Bandhan",
    "2026-09-04": "Sri Krishna Astami",
    "2026-09-14": "Vinayaka Chaturthi",
    "2026-10-02": "Mahatma Gandhi Jayanti",
    "2026-10-19": "Durga Ashtami",
    "2026-10-20": "Dusshera / Dasara",
    "2026-11-08": "Deepavali / Diwali Break",
    "2026-11-24": "Guru Nanak Jayanti",
    "2026-12-23": "Kisan Diwas",
    "2026-12-25": "Christmas",
    "2027-01-01": "New Year Day",
    "2027-01-14": "Sankranti / Pongal Break",
    "2027-01-15": "Kanuma",
    "2027-01-26": "Republic Day",
    "2027-03-08": "Maha Shivratri",
    "2027-03-25": "Holi",
    "2027-03-30": "Ugadi (Telugu New Year)",
    "2027-04-09": "Good Friday",
    "2027-04-14": "Dr. B.R. Ambedkar Jayanti",
    "2027-05-01": "May Day"
}

def get_dynamic_upcoming_schedule(start_date=None, count=12):
    from datetime import timedelta
    if start_date is None:
        start_date = datetime.now()
    
    upcoming_all = []
    upcoming_gazetted = []
    
    curr = start_date + timedelta(days=1)
    while len(upcoming_all) < count and curr < start_date + timedelta(days=120):
        d_str = curr.strftime("%Y-%m-%d")
        day_name = curr.strftime("%A")
        date_formatted = curr.strftime("%d %B %Y")
        is_official = d_str in OFFICIAL_UNIVERSITY_HOLIDAYS
        is_sunday = curr.weekday() == 6
        is_saturday = curr.weekday() == 5

        if is_official:
            name = OFFICIAL_UNIVERSITY_HOLIDAYS[d_str]
            entry_txt = f"{day_name}, {date_formatted} - {name} (Official University Holiday)"
            upcoming_all.append(entry_txt)
            upcoming_gazetted.append(f"{day_name}, {date_formatted} - {name}")
        elif is_sunday or is_saturday:
            entry_txt = f"{day_name}, {date_formatted} - Weekend ({day_name})"
            upcoming_all.append(entry_txt)
            
        curr += timedelta(days=1)
        
    return upcoming_all, upcoming_gazetted

def get_current_time_context(query: str = "") -> str:
    """Generate dynamic real-time clock context and live calendar schedule."""
    now = datetime.now()
    base_time = f"Time Context: {now.strftime('%I:%M %p, %A, %d %B %Y')}. Lecture Hours: 09:30 AM - 05:30 PM."
    
    all_breaks, gazetted = get_dynamic_upcoming_schedule(now, count=12)
    all_breaks_text = "\n".join([f"  {idx}. {item}" for idx, item in enumerate(all_breaks[:10], 1)])
    gazetted_text = "\n".join([f"  {idx}. {item}" for idx, item in enumerate(gazetted[:6], 1)])
    
    calendar_block = f"""
REAL-TIME DYNAMIC CALENDAR & HOLIDAYS SCHEDULE (Live calculated from Today: {now.strftime('%A, %d %B %Y')}):
- Official Academic Calendar Link: https://sraap.in/acb_uploads/2026-27_1_BTECH_20260804.pdf
- Next Upcoming Holidays INCLUDING Saturdays and Sundays:
{all_breaks_text}
- Next Official Gazetted University Holidays (Excluding ordinary weekends):
{gazetted_text}
- Academic Calendar Semester Dates:
  * 27 - 28 November 2026: End-Term Practical / Lab Examinations
  * 28 November 2026 (Saturday): Last Working Day of Odd Semester
  * 30 November - 05 December 2026: Regular End-Term Theory Examinations (SEE)
  * 11 December 2026: Declaration of Results
  * 01 January 2027: Even Semester 2026-27 Commencement
  * 04 January 2027: First Teaching Day of Even Semester
"""
    return f"{base_time}\n{calendar_block}"

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
- Dean of School of CS & AI: Prof. M. Sheshikala (Email: m.sheshikala@sru.edu.in, Cabin: Dean Office, School of Computer Science & Artificial Intelligence, Block 11)
- Head of Department (CSE / CS & AI): Dr. Ch. Sandeep (Email: sandeep.ch@sru.edu.in, Cabin: Head of Department Office, School of Computer Science & Artificial Intelligence, Block 11)
Never state that the Governor of Tamil Nadu or any governor is the Chancellor.

Campus Facilities & Policies:
- Central Library Working Hours (Warangal Campus):
  * Weekdays (Monday to Friday): 8:00 a.m. to 8:00 p.m.
  * Saturdays, Sundays, and Holidays: 10:00 a.m. to 4:00 p.m.
  * Reading Hall: Open daily from 8:00 a.m. to 10:00 p.m.
- Sports & Fitness Facilities: Indoor Sports Complex (Badminton, Table Tennis, Chess, Carroms), Outdoor Sports Grounds (Cricket Ground, Football Field, Basketball Courts, Volleyball Courts), Gymnasium, and Yoga & Meditation Hall.
  * IMPORTANT: SR University does NOT have a swimming pool on campus.
- Official Fee Payment Portals:
  * Academic Fees, Tuition Fees, and Hostel Dues: Paid online via the official university payment portal at https://sruniv.com/
  * End Semester Examination Fees, Convocation Fee, and Condonation Fee: Paid through the student SRAAP portal at https://sraap.in/ (or https://sraap.in/student_login.php)
  Always clearly distinguish between these two portals when answering questions about fees, tuition, hostel dues, end semester fees, convocation fees, or condonation fees.
- Student Batch Mentorship System:
  * Batch Size & Allocation: Every batch has 30 members/students, and a dedicated faculty mentor is assigned to each batch.
  * Mentor Support & Academic Help: The mentor guides students through academic-related issues, course concerns, attendance, study planning, and general counseling.
  * Leaving Campus Prior (Early Exit): Students can leave the campus prior to normal closing hours by obtaining their assigned mentor's signature/approval on an early exit gate pass.
  * Checking Mentor Details: Students can check their assigned mentor's details (faculty name, cabin, email) directly on their student SRAAP dashboard at https://sraap.in/ (or https://sraap.in/student_login.php).
- Campus Map & Room Navigation Guide:
  * Official Campus Map Overview: When a user asks map-related questions or questions about block locations (e.g., 'campus map', 'where is block 11', 'where is block 10', 'where is block 1', 'how to find a room', 'room 3201', 'campus layout', 'directions'):
    Reference and embed the official map:
    You can refer to the following map overview of SR University campus:
    ![SR University Campus Map](/map_overview.png)
  * Room Numbering Navigation System (Tip):
    - For Blocks 1 to 9 (4-digit room numbers, e.g. 3201):
      * 1st digit: Block number (e.g., 3 indicates Block 3)
      * 2nd digit: Floor (e.g., 2 indicates 2nd Floor)
      * Last 2 digits: Room number (e.g., 01 indicates Room 01)
    - For Blocks 10 & 11 (5-digit room numbers, e.g. 11201 or 10105):
      * 1st and 2nd digits: Block number (e.g., 11 indicates Block 11, 10 indicates Block 10)
      * 3rd digit: Floor (e.g., 2 indicates 2nd Floor, 1 indicates 1st Floor)
      * Last 2 digits: Room number (e.g., 01 indicates Room 01, 05 indicates Room 05)
- SSM Gamification / Coin Certificate Uploads: Certificates for SSM / Gamification coins must be uploaded via the official university portal at https://www.sruniv.com (under the Student SSM / Gamification section).
- SSM Alpha & Sigma Coin Claims & Redemptions (Official Coin Costs):
  1. Coffee with VC: 1,000 Alpha / Sigma Coins
  2. Coffee with Dean: 500 Alpha / Sigma Coins
  3. Photograph with VC: 1,000 Alpha / Sigma Coins
  4. Meeting with Industry / International Delegates: 1,000 Alpha / Sigma Coins
  5. Social Media Post about Approved Student Achievement: 1,000 Alpha / Sigma Coins
  6. Teaching Assistant (TA) Recommendation (if Approved): 1,000 Alpha / Sigma Coins
  7. Committee Member Recommendation: 1,000 Alpha / Sigma Coins
  8. Lab / Equipment Access for 1 Day (if Available): 1,000 Alpha / Sigma Coins
  9. Batch Change Recommendation (if Approved): 1,000 Alpha / Sigma Coins
  10. Change of Project / Research Mentorship Guidance (if Approved): 1,000 Alpha / Sigma Coins
  11. Approval of Attending Workshop Outside SRU: 500 Alpha / Sigma Coins
- Project Developers & Capstone Credits: This AI Helpdesk was engineered and developed by Keerthi Surya Teja, Bijjala Vrindha, Boga Siri Chandana, and Burra Praneeth as their B.Tech Capstone Project under the mentorship of Dr. Sridhar Chintala (Associate Professor, Director, AI&DL) at the School of Computer Science & Artificial Intelligence, SR University, Warangal (Academic Year 2026-2027).

Core rules:
1. Output concise, factual plain text. Use separate lines for lists. Do NOT use markdown (no asterisks, no hashes, no bold), except for embedding the campus map image tag ![SR University Campus Map](/map_overview.png) when answering map or block location queries.
2. PRIVACY: Never output personal mobile or phone numbers. Provide only official email addresses, cabin numbers, or departments.
3. When asked about an individual faculty, staff, or officer (e.g. 'who is Dr. Sridhar Chintala', 'who is Dean of Computer Science'):
   State their full name, their designation/role, official email, and complete cabin/room location directly from the records without cutting off.
4. When multiple faculty or staff match a query: list only their names (one per line). Do not dump emails/cabins unless specifically requested.
5. Academic Calendar link: https://sraap.in/acb_uploads/2026-27_1_BTECH_20260804.pdf. Never use expired links.
6. Dynamic Calendar & Holidays:
   - When asked for upcoming holidays (including or excluding Saturdays and Sundays):
     Directly answer with the exact requested number of upcoming dates from the REAL-TIME DYNAMIC CALENDAR SCHEDULE in the context.
     Format as a clear numbered list with day, date, and reason (e.g., 1. Saturday, 21 November 2026 - Weekend (Saturday)).
     Never claim that Saturday or Sunday dates are not listed; the dynamic calendar context provides the exact dates.
7. Information Sources & Reasoning:
   - Always prioritize the OFFICIAL UNIVERSITY DATABASE RECORDS.
   - If database records are limited or external web search results are provided in the context, reason logically and provide a helpful, factual answer based on the web results instead of a generic negative answer.
   - Only say "No matching university record found" if neither database records nor web search provide any relevant information.
"""

import html as html_lib
import urllib.parse

def search_web_ddg(query: str, max_results: int = 3) -> List[str]:
    """Perform a live web search via DuckDuckGo Lite to retrieve real-time external university information."""
    clean_q = query.strip()
    if "sr university" not in clean_q.lower() and "sru" not in clean_q.lower() and "warangal" not in clean_q.lower():
        search_term = f"{clean_q} SR University Warangal"
    else:
        search_term = clean_q
    
    url = "https://lite.duckduckgo.com/lite/"
    data = urllib.parse.urlencode({"q": search_term}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=4.5) as r:
            raw_html = r.read().decode("utf-8", errors="ignore")
            snippets = re.findall(r'<td[^>]*class=[\'"]result-snippet[\'"][^>]*>(.*?)</td>', raw_html, re.DOTALL)
            clean = [html_lib.unescape(re.sub(r'<[^>]+>', '', s)).strip() for s in snippets]
            clean = [re.sub(r'\s+', ' ', s) for s in clean if len(s) > 20]
            return clean[:max_results]
    except Exception as e:
        logger.warning(f"Web search warning: {e}")
        return []

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

    # Protect markdown images ![alt](url) from having brackets removed
    images = []
    def _img_repl(m):
        images.append(m.group(0))
        return f"@@@IMGTOKEN{len(images)-1}@@@"
    text = re.sub(r'!\[.*?\]\([^\)]+\)', _img_repl, text)

    # Protect URLs from having underscores/characters removed
    urls = []
    def _url_repl(m):
        urls.append(m.group(0))
        return f"@@@URLTOKEN{len(urls)-1}@@@"

    text = re.sub(r'https?://[^\s]+', _url_repl, text)

    # Remove markdown bold/italic/header symbols (without touching protected URLs or images)
    cleaned = re.sub(r"[\*#_`~\[\]]", "", text)

    # Restore URLs and images
    for idx, u in enumerate(urls):
        cleaned = cleaned.replace(f"@@@URLTOKEN{idx}@@@", u)
    for idx, img in enumerate(images):
        cleaned = cleaned.replace(f"@@@IMGTOKEN{idx}@@@", img)

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
    "fee": ["fee", "fees", "payment", "accounts", "dues", "tuition"],
    "fees": ["fee", "fees", "payment", "accounts", "dues", "tuition"],
    "tuition": ["tuition", "fee", "fees", "payment", "dues", "sruniv"],
    "payment": ["fee", "fees", "payment", "dues", "receipt", "receipts", "tuition"],
    "receipt": ["fee", "fees", "payment", "dues", "receipt", "receipts"],
    "convocation": ["convocation", "fee", "sraap", "certificate"],
    "condonation": ["condonation", "fee", "attendance", "medical", "sraap"],
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
    "calendar": ["calendar", "academic calendar", "semester dates", "schedule", "exams"],
    "mentor": ["mentor", "mentors", "mentorship", "batch", "gate pass", "sraap", "counselor"],
    "mentors": ["mentor", "mentors", "mentorship", "batch", "gate pass", "sraap", "counselor"],
    "mentorship": ["mentor", "mentors", "mentorship", "batch", "gate pass", "sraap"],
    "batch": ["batch", "batches", "mentor", "mentors", "30 members", "sraap"]
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

    # Developer / Credits quick check
    if any(p in q_lower for p in ["who developed you", "who made you", "who created you", "who built you", "who developed this", "developers", "credits", "who are the developers"]):
        ans = ("The SR University AI Helpdesk was engineered and developed by Keerthi Surya Teja, "
               "Bijjala Vrindha, Boga Siri Chandana, and Burra Praneeth as part of their B.Tech Capstone Project "
               "under the guidance of Dr. Sridhar Chintala (Associate Professor, Director, AI&DL) at the "
               "School of Computer Science & Artificial Intelligence, SR University, Warangal (Academic Year 2026-2027).")
        t_end = time.perf_counter()
        timings["rag_ms"] = 0.0
        timings["llm_ms"] = 0.0
        timings["total_ms"] = (t_end - t_start) * 1000
        return ans, [], timings

    # Step 2: Try AI-first pipeline with Groq LLM
    groq_key = os.getenv("GROQ_API_KEY")
    t_llm_start = time.perf_counter()

    if groq_key and groq_key.strip():
        result = _ai_first_pipeline(q_clean, session_id, db, groq_key.strip(), timings, t_start)
        if result is not None:
            return result

    # Step 3: Fallback - when LLM is unavailable
    logger.info("[FALLBACK] LLM unavailable, using keyword fallback")

    # Dynamic fallback check for holiday/weekend queries
    q_low = q_clean.lower()
    if any(w in q_low for w in ["holiday", "holidays"]) and any(w in q_low for w in ["upcoming", "next", "saturday", "sunday", "weekend", "five", "5", "three", "3"]):
        all_breaks, gazetted = get_dynamic_upcoming_schedule(datetime.now(), count=12)
        include_wk = any(w in q_low for w in ["saturday", "sunday", "weekend", "including"])
        chosen = all_breaks if include_wk else gazetted
        count = 5
        if "three" in q_low or " 3 " in q_low: count = 3
        elif "ten" in q_low or " 10 " in q_low: count = 10
        elif "five" in q_low or " 5 " in q_low: count = 5

        formatted_list = "\n".join([f"{idx}. {item}" for idx, item in enumerate(chosen[:count], 1)])
        cal_url = "https://sraap.in/acb_uploads/2026-27_1_BTECH_20260804.pdf"
        ans = f"Based on the current date ({datetime.now().strftime('%A, %d %B %Y')}), here are the next upcoming holidays{' including weekends' if include_wk else ''}:\n\n{formatted_list}\n\nOfficial Academic Calendar: {cal_url}"
        t_end = time.perf_counter()
        timings["rag_ms"] = 0.0
        timings["llm_ms"] = (t_end - t_llm_start) * 1000
        timings["total_ms"] = (t_end - t_start) * 1000
        return clean_plain_text(ans), [], timings

    t_search_start = time.perf_counter()
    matched_records = search_database(q_clean, db, category="all")
    t_search_end = time.perf_counter()
    timings["rag_ms"] = (t_search_end - t_search_start) * 1000
    timings["llm_ms"] = (t_search_start - t_llm_start) * 1000
    timings["total_ms"] = (t_search_end - t_start) * 1000

    if not matched_records or matched_records[0]["score"] < 15:
        web_res = search_web_ddg(q_clean, max_results=2)
        if web_res:
            ans = "According to SR University campus information:\n\n" + "\n\n".join(web_res)
            return clean_plain_text(ans), [], timings
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
    dynamic_prompt = f"{get_current_time_context(query)}\n{SYSTEM_PROMPT}"
    messages = [{"role": "system", "content": dynamic_prompt}]

    has_strong_match = bool(pre_records and pre_records[0].get("score", 0) >= 12)

    if pre_records:
        context_items = [f"- {r['text'][:650]}" for r in pre_records[:5]]
        instruction = "OFFICIAL UNIVERSITY DATABASE RECORDS (Verified facts for this query - answer directly using these records):\n" if has_strong_match else "POTENTIAL DATABASE MATCHES:\n"
        messages.append({
            "role": "system",
            "content": instruction + "\n".join(context_items)
        })

    # Web search integration: If no strong database match or for campus facilities/general topics, fetch web snippets
    web_snippets = []
    if not has_strong_match or any(w in query.lower() for w in ["sports", "facility", "facilities", "hostel", "mess", "placement", "bus", "transport", "canteen", "ranking", "nirf"]):
        web_snippets = search_web_ddg(query, max_results=3)

    if web_snippets:
        messages.append({
            "role": "system",
            "content": "LIVE EXTERNAL WEB SEARCH RESULTS (Use to supplement answer or when database has no record):\n" + "\n".join([f"- {s}" for s in web_snippets])
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
                "max_tokens": 800,
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
                results_text = "\n".join([f"- {r['text'][:650]}" for r in matched_records[:6]])
            else:
                web_snippets = search_web_ddg(search_query, max_results=3)
                if web_snippets:
                    results_text = "No direct database match. Web search results:\n" + "\n".join([f"- {s}" for s in web_snippets])
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
                max_tokens=800,
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
