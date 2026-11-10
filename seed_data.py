from database import (
    SessionLocal, init_db,
    Faculty, AdministrativePersonnel, StudentClub, CollegeWebsite
)

SAMPLE_FACULTY = [
    {
        "emp_id": "SRU-CSE-101",
        "name": "Dr. A. Ramesh Babu",
        "email": "a.rameshbabu@sru.edu.in"
    },
    {
        "emp_id": "SRU-ECE-102",
        "name": "Dr. P. Sunitha Rao",
        "email": "p.sunitha@sru.edu.in"
    },
    {
        "emp_id": "SRU-MECH-103",
        "name": "Dr. K. Srinivas",
        "email": "k.srinivas@sru.edu.in"
    },
    {
        "emp_id": "SRU-BS-104",
        "name": "Dr. M. Lakshmi",
        "email": "m.lakshmi@sru.edu.in"
    },
    {
        "emp_id": "SRU-CSE-105",
        "name": "Prof. Vikram Reddy",
        "email": "vikram.reddy@sru.edu.in"
    },
    {
        "emp_id": "SRU-CIVIL-106",
        "name": "Dr. G. Radhakrishna",
        "email": "g.radhakrishna@sru.edu.in"
    },
    {
        "emp_id": "SRU-MBA-107",
        "name": "Dr. S. Kavitha",
        "email": "s.kavitha@sru.edu.in"
    },
    {
        "emp_id": "SRU-CSE-108",
        "name": "Dr. Sridhar Ch",
        "email": "sridhar.ch@sru.edu.in"
    },
    {
        "emp_id": "SRU-ECE-109",
        "name": "Dr. Sridhar E",
        "email": "sridhar.e@sru.edu.in"
    }
]

SAMPLE_ADMIN = [
    {
        "role": "Buses In-Charge / Transport Coordinator",
        "name": "Mr. Ch. Venkat Narayana",
        "email": "transport@sru.edu.in",
        "cabin_room_number": "Cabin T-102, Ground Floor, Transport Cell"
    },
    {
        "role": "Fees & Accounts Section Officer",
        "name": "Mr. T. Mallikarjun Rao",
        "email": "accounts@sru.edu.in",
        "cabin_room_number": "Cabin A-204, Admin Block, 2nd Floor"
    },
    {
        "role": "Hostel Warden (Boys)",
        "name": "Mr. B. Suresh Kumar",
        "email": "hostel.boys@sru.edu.in",
        "cabin_room_number": "Hostel Block-A, Office Room 1"
    },
    {
        "role": "Hostel Warden (Girls)",
        "name": "Mrs. D. Padmaja",
        "email": "hostel.girls@sru.edu.in",
        "cabin_room_number": "Girls Hostel Pearl, Warden Office"
    },
    {
        "role": "Admissions & Counseling Officer",
        "name": "Mr. R. Praveen",
        "email": "admissions@sru.edu.in",
        "cabin_room_number": "Admin Block, Cabin AD-101"
    },
    {
        "role": "Controller of Examinations (CoE)",
        "name": "Dr. N. Chandrasekhar",
        "email": "examcell@sru.edu.in",
        "cabin_room_number": "Exam Branch, 1st Floor, Room EB-105"
    },
    {
        "role": "Sports & Physical Education Director",
        "name": "Mr. J. Mohan Das",
        "email": "sports@sru.edu.in",
        "cabin_room_number": "Indoor Sports Complex, Room S-01"
    }
]

SAMPLE_CLUBS = [
    {
        "club_name": "RoboSRU - Robotics & IoT Club",
        "social_media_link": "https://instagram.com/sru_robotics_club"
    },
    {
        "club_name": "CodeChef SRU Chapter / Coding Club",
        "social_media_link": "https://instagram.com/sru_coders"
    },
    {
        "club_name": "Spark Cultural & Arts Club",
        "social_media_link": "https://instagram.com/sru_spark_arts"
    },
    {
        "club_name": "IEEE SRU Student Branch",
        "social_media_link": "https://linkedin.com/company/ieee-sru-branch"
    },
    {
        "club_name": "Rotaract Club of SRU",
        "social_media_link": "https://instagram.com/rotaract_sru"
    },
    {
        "club_name": "GDG on Campus (Google Developer Groups)",
        "social_media_link": "https://instagram.com/gdg_sru"
    },
    {
        "club_name": "SRU Sports & Athletics Club",
        "social_media_link": "https://instagram.com/sru_sports"
    }
]

SAMPLE_WEBSITES = [
    {
        "url": "https://sru.edu.in",
        "purpose_tags": "official university website, general overview, campus updates, vision, news, admissions information"
    },
    {
        "url": "https://erp.sru.edu.in",
        "purpose_tags": "student erp portal, attendance check, internal marks, academic calendar, student profile"
    },
    {
        "url": "https://feepay.sru.edu.in",
        "purpose_tags": "tuition fee payment, semester fees, bus fee, hostel fee, payment receipts, accounts"
    },
    {
        "url": "https://lms.sru.edu.in",
        "purpose_tags": "learning management system, course materials, assignments, lecture notes, syllabus, digital classroom"
    },
    {
        "url": "https://examcell.sru.edu.in",
        "purpose_tags": "hall ticket download, semester exam timetable, exam results, revaluation, grade cards"
    },
    {
        "url": "https://placement.sru.edu.in",
        "purpose_tags": "campus placements, recruiter visits, internship drives, placement statistics, career guidance"
    },
    {
        "url": "https://library.sru.edu.in",
        "purpose_tags": "digital library, IEEE Xplore, e-books, research journals, catalogue, book search"
    }
]


import os
import logging
from database import (
    SessionLocal, init_db,
    Faculty, AdministrativePersonnel, StudentClub, CollegeWebsite
)
from import_real_data import import_all_data

logger = logging.getLogger("seed_data")

def seed_database(force: bool = False):
    init_db()
    db = SessionLocal()
    try:
        faculty_count = db.query(Faculty).count()
        admin_count = db.query(AdministrativePersonnel).count()
        clubs_count = db.query(StudentClub).count()
        websites_count = db.query(CollegeWebsite).count()

        # If empty or force mode, import real data
        if force or (faculty_count == 0 and admin_count == 0):
            print("Importing real data from data folder...")
            import_all_data(db, force=force)
            print("Real data imported successfully!")
        else:
            print(f"Database already populated: {faculty_count} faculty, {admin_count} admin, {clubs_count} clubs, {websites_count} websites.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database(force=True)
