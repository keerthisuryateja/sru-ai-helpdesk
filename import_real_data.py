import os
import json
import re
import logging
from sqlalchemy.orm import Session
from database import (
    SessionLocal, init_db, engine, Base,
    Faculty, AdministrativePersonnel, StudentClub, CollegeWebsite, UniversityKnowledge
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("import_real_data")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def load_json(filename: str):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        logger.warning(f"File not found: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_email_from_name(name: str) -> str:
    """Generate official institutional email from person's name for privacy compliance."""
    clean = re.sub(r'^(dr\.|prof\.|mr\.|mrs\.|ms\.)\s*', '', name.strip(), flags=re.IGNORECASE)
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', clean).strip().lower()
    parts = clean.split()
    if len(parts) >= 2:
        return f"{parts[0]}.{parts[-1]}@sru.edu.in"
    elif len(parts) == 1:
        return f"{parts[0]}@sru.edu.in"
    return "faculty@sru.edu.in"

def import_all_data(db: Session, force: bool = True):
    if force:
        logger.info("Clearing existing records for fresh import...")
        db.query(Faculty).delete()
        db.query(AdministrativePersonnel).delete()
        db.query(StudentClub).delete()
        db.query(CollegeWebsite).delete()
        db.query(UniversityKnowledge).delete()
        db.commit()

    # =========================================================================
    # 1. Faculty Import (Privacy Compliant: Email & Cabin Only, No Phone Numbers)
    # =========================================================================
    logger.info("Importing Faculty records (Privacy compliant)...")
    
    # Map known directory emails
    contact_dir = load_json("contact_directory.json") or []
    email_lookup = {}
    for item in contact_dir:
        p_name = (item.get("concerned_person") or "").strip().lower()
        em = (item.get("email") or "").strip()
        if p_name and em:
            email_lookup[p_name] = em
        for c in item.get("contacts", []):
            cp_name = (c.get("concerned_person") or "").strip().lower()
            c_em = (c.get("email") or "").strip()
            if cp_name and c_em:
                email_lookup[cp_name] = c_em

    all_faculty = load_json("faculty_directory.json") or []
    inserted_emp_ids = set()
    faculty_objects = []

    for f in all_faculty:
        raw_id = str(f.get("id", "")).strip()
        name = f.get("name", "").strip()
        if not raw_id or not name or raw_id in inserted_emp_ids:
            continue

        clean_lower = name.lower()
        matched_email = None
        for k, v in email_lookup.items():
            if k in clean_lower or clean_lower in k:
                matched_email = v
                break

        email = matched_email or generate_email_from_name(name)

        faculty_objects.append(Faculty(
            emp_id=raw_id,
            name=name,
            email=email,
            cabin_id=None
        ))
        inserted_emp_ids.add(raw_id)

    db.bulk_save_objects(faculty_objects)
    db.commit()
    logger.info(f"Inserted {len(faculty_objects)} Faculty records.")

    # Build fast faculty email lookup
    faculty_email_by_name = {}
    for f in faculty_objects:
        clean_n = f.name.lower().replace("dr.", "").replace("prof.", "").replace("mr.", "").replace("mrs.", "").replace("ms.", "").strip()
        faculty_email_by_name[clean_n] = f.email

    # =========================================================================
    # 2. Administrative Personnel Import (Email & Cabin/Room Only, No Phone Numbers)
    # =========================================================================
    logger.info("Importing Administrative Personnel (Privacy compliant)...")
    admin_objects = []
    seen_admin_pairs = set()

    def add_admin(role: str, name: str, email: str, cabin: str):
        key = (role.strip().lower(), name.strip().lower())
        if key in seen_admin_pairs:
            return
        seen_admin_pairs.add(key)
        admin_objects.append(AdministrativePersonnel(
            role=role.strip()[:145],
            name=name.strip()[:145],
            email=(email or "office@sru.edu.in").strip()[:115],
            cabin_room_number=(cabin or "Main Admin Block").strip()[:45]
        ))

    # A. From contact_directory.json
    for item in contact_dir:
        svc = item.get("service_or_facility") or "Administrative Service"
        if "contacts" in item and isinstance(item["contacts"], list):
            for c in item["contacts"]:
                add_admin(
                    role=svc,
                    name=c.get("concerned_person") or "In-charge",
                    email=c.get("email") or "office@sru.edu.in",
                    cabin=c.get("location") or "Main Admin Block"
                )
        else:
            if item.get("concerned_person"):
                add_admin(
                    role=svc,
                    name=item.get("concerned_person"),
                    email=item.get("email") or "office@sru.edu.in",
                    cabin=item.get("location") or "Main Admin Block"
                )

    # B. From department_heads.json
    hods_data = load_json("department_heads.json") or {}
    for section_name, entries in hods_data.items():
        for role_title, person_name in entries.items():
            if role_title == "sources":
                continue
            clean_n = person_name.lower().replace("dr.", "").replace("prof.", "").replace("mr.", "").replace("mrs.", "").replace("ms.", "").strip()
            email = faculty_email_by_name.get(clean_n, generate_email_from_name(person_name))
            add_admin(
                role=f"{role_title} ({section_name})",
                name=person_name,
                email=email,
                cabin=f"{section_name} Office"
            )

    # C. From dean_positions.json
    dean_positions = load_json("dean_positions.json") or []
    for dp in dean_positions:
        pos = dp.get("position")
        fac = dp.get("faculty")
        if pos and fac:
            clean_n = fac.lower().replace("dr.", "").replace("prof.", "").replace("mr.", "").replace("mrs.", "").replace("ms.", "").strip()
            email = faculty_email_by_name.get(clean_n, generate_email_from_name(fac))
            add_admin(
                role=pos,
                name=fac,
                email=email,
                cabin="University Administration"
            )

    # D. From club_coordinators.json
    clubs_coord = load_json("club_coordinators.json") or {}
    admin_coord = clubs_coord.get("university_club_administration", {})
    if "head_of_clubs" in admin_coord:
        add_admin(
            role="Head of Clubs / Student Activity Affairs",
            name=admin_coord["head_of_clubs"],
            email="studentaffairs@sru.edu.in",
            cabin="Student Activity Center"
        )

    for tc in clubs_coord.get("technical_clubs", []):
        c_name = tc.get("name", "")
        fac = tc.get("faculty_in_charge", "")
        desig = tc.get("designation", "Faculty Coordinator")
        if c_name and fac:
            clean_n = fac.lower().replace("dr.", "").replace("prof.", "").replace("mr.", "").replace("mrs.", "").replace("ms.", "").strip()
            email = faculty_email_by_name.get(clean_n, generate_email_from_name(fac))
            add_admin(
                role=f"{desig} - {c_name}",
                name=fac,
                email=email,
                cabin="Student Activity Center"
            )

    for ntc in clubs_coord.get("non_technical_clubs", []):
        c_name = ntc.get("name", "")
        fac = ntc.get("faculty_in_charge", "")
        desig = ntc.get("designation", "Faculty Coordinator")
        if c_name and fac:
            clean_n = fac.lower().replace("dr.", "").replace("prof.", "").replace("mr.", "").replace("mrs.", "").replace("ms.", "").strip()
            email = faculty_email_by_name.get(clean_n, generate_email_from_name(fac))
            add_admin(
                role=f"{desig} - {c_name}",
                name=fac,
                email=email,
                cabin="Student Activity Center"
            )

    # Add Placement Director and Transport In-Charge explicitly
    add_admin(
        role="Director of Training & Placements",
        name="Mr. GuruCharn Singh",
        email="director.placements@sru.edu.in",
        cabin="Training & Placement Block"
    )
    add_admin(
        role="Buses & Transport In-Charge",
        name="Mr. Ch. Venkat Narayana",
        email="transport@sru.edu.in",
        cabin="Cabin T-102, Ground Floor, Transport Cell"
    )

    db.bulk_save_objects(admin_objects)
    db.commit()
    logger.info(f"Inserted {len(admin_objects)} Administrative Personnel records.")

    # =========================================================================
    # 3. Student Clubs Import (clubs.json)
    # =========================================================================
    logger.info("Importing Student Clubs...")
    clubs_data = load_json("clubs.json") or {}
    club_objects = []
    seen_clubs = set()

    all_clubs_list = (
        clubs_data.get("technical_clubs", []) +
        clubs_data.get("non_technical_clubs", [])
    )

    for c in all_clubs_list:
        c_name = c.get("name", "").strip()
        url = c.get("url", "").strip()
        if c_name and c_name not in seen_clubs:
            seen_clubs.add(c_name)
            club_objects.append(StudentClub(
                club_name=c_name[:145],
                social_media_link=url[:250]
            ))

    db.bulk_save_objects(club_objects)
    db.commit()
    logger.info(f"Inserted {len(club_objects)} Student Club records.")

    # =========================================================================
    # 4. University Knowledge Base Import (Fees, Rules, Permissions, Events, etc.)
    # =========================================================================
    logger.info("Importing University Knowledge base...")
    knowledge_data = load_json("university_knowledge.json") or []
    knowledge_objects = []

    for item in knowledge_data:
        knowledge_objects.append(UniversityKnowledge(
            category=item.get("category", "general")[:95],
            title=item.get("title", "")[:195],
            content=item.get("content", ""),
            tags=item.get("tags", "")
        ))

    db.bulk_save_objects(knowledge_objects)
    db.commit()
    logger.info(f"Inserted {len(knowledge_objects)} University Knowledge records.")

    # =========================================================================
    # 5. College Websites Import (Enriched from https://sru.edu.in/)
    # =========================================================================
    logger.info("Importing College Websites...")
    websites_objects = []
    seen_urls = set()

    def add_website(url: str, tags: str):
        u = url.strip()
        if u and u not in seen_urls:
            seen_urls.add(u)
            websites_objects.append(CollegeWebsite(
                url=u[:250],
                purpose_tags=tags.strip()
            ))

    # Core academic & payment portals
    add_website("https://sraap.in/acb_uploads/2026-27_1_BTECH_20260804.pdf", "academic calendar, semester dates, exam schedules, holidays, academic year calendar")
    add_website("https://sraap.in/student_login.php", "student login portal, SRAAP, view attendance, course registration, exam fees payment, student credentials, out pass")
    add_website("https://sruniv.com/", "fee payment portal, tuition fees payment, exam fees, dues, online payment, fee receipts")

    # Scraped & verified official university portals
    add_website("https://sru.edu.in", "official university website, campus overview, announcements, vision, news")
    add_website("https://sru.edu.in/fee-scholarship/", "fee structure, tuition fees per semester, merit scholarships, special scholarships, hostel fees, AC non AC rooms, admission fee, specialization fee")
    add_website("https://sru.edu.in/campus-life/", "campus life, student facilities, annual fests, Sparkrill, Navadhara, PRAGATHI project expo, dining, sports complex, health center, medical emergency")
    add_website("https://sru.edu.in/placements/", "campus placements, highest package 51 LPA, average package, top recruiting companies, placement statistics, placement director, internships")
    add_website("https://sru.edu.in/admission/", "admissions portal, apply online, entrance exam, eligibility criteria, BTech, MTech, MBA, MCA, PhD admissions")
    add_website("https://sru.edu.in/statutory_committees/", "statutory committees, anti-ragging committee, anti-drug committee, POSH committee, student discipline committee, proctorial committee")
    add_website("https://sru.edu.in/statutory_committees/anti-ragging_committee.php", "anti-ragging committee, zero tolerance policy, complaint redressal, campus safety, anti-ragging squad")
    add_website("https://sru.edu.in/statutory_committees/anti_drug_committee.php", "anti-drug committee, drug-free campus, tobacco-free zone, discipline rules, campus security")
    add_website("https://sru.edu.in/statutory_committees/students_discipline_committee.php", "student discipline committee, code of conduct, campus rules, ID card rule, dress code, disciplinary actions")
    add_website("https://sru.edu.in/statutory_committees/proctorial_committee.php", "proctorial committee, campus permissions, gate pass oversight, hostel curfew, out pass policy")
    add_website("https://sru.edu.in/academics/schools/school-of-cse-ai/", "School of Computer Science & AI, CSE specializations, AI/ML, cyber security, data science, robotics, gaming ARVR")
    add_website("https://sru.edu.in/academics/schools/school-of-engineering/", "School of Engineering, ECE, EEE, Mechanical, Civil engineering departments, labs, faculty")
    add_website("https://sru.edu.in/academics/schools/astra-school-of-business/", "Astra School of Business, MBA, BBA specializations, marketing, finance, HR, business analytics")
    add_website("https://sru.edu.in/visit-us", "visit campus, campus address Ananthasagar Hasanparthy Warangal, campus tour, contact desk, official email info@sru.edu.in")

    # Student Success Management (SSM) Gamification Portals
    add_website("https://sruniv.com/public/student/ssm/alpha-coins", "SSM Alpha Coins, academic gamification, curricular coins, hackathon coins, research publication coins, certifications, grades, attendance coins")
    add_website("https://sruniv.com/public/student/ssm/sigma-coins", "SSM Sigma Coins, extracurricular gamification, non-academic coins, sports coins, leadership, student council, startups, NCC, NSS, volunteering")
    add_website("https://sruniv.com/public/student/ssm/leaderboard", "SSM Leaderboard, gamification ranking, top students leaderboard, coin scores, badge leaderboard, competitive ranking, campus ranking")
    add_website("https://sruniv.com/public/student/ssm/penalty-coins", "SSM Penalty Coins, coin deductions, discipline deductions, cheating plagiarism penalty, grade F coin reduction, misbehavior penalty")
    add_website("https://sruniv.com/public/student/ssm/redeem", "SSM Coin Redemption, redeem coins, coffee with VC, deadline extension, extra quiz attempt, goodies, workshop refund, perks, privileges")

    db.bulk_save_objects(websites_objects)
    db.commit()
    logger.info(f"Inserted {len(websites_objects)} College Website records.")

    print("\n--- Summary of Inserted Real Data ---")
    print(f"Faculty: {db.query(Faculty).count()}")
    print(f"Administrative Personnel: {db.query(AdministrativePersonnel).count()}")
    print(f"Student Clubs: {db.query(StudentClub).count()}")
    print(f"University Knowledge Articles: {db.query(UniversityKnowledge).count()}")
    print(f"College Websites: {db.query(CollegeWebsite).count()}")

if __name__ == "__main__":
    init_db()
    session = SessionLocal()
    try:
        import_all_data(session, force=True)
    finally:
        session.close()
