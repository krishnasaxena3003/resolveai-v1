"""Clearly labelled sample data for demos. Run: python seed.py"""
from ai_service import fallback_analysis
from database import init_db
from ticket_service import create_ticket, list_tickets
from database import connect
from sample_data import SAMPLE_REPORTS

SAMPLES = [(description, location) for _, description, location in SAMPLE_REPORTS]

DEMO = [("student", "Demo Student", "student@demo.test", "DemoPass123", None),
        ("staff", "Demo Staff", "staff@demo.test", "DemoPass123", None),
        ("worker", "Demo Worker", "worker@demo.test", "DemoPass123", "Electrical Maintenance")]


def seed_sample_tickets(db_path=None) -> int:
    """Create missing members of the ten-ticket demo set, without duplicating prior samples."""
    init_db(db_path)
    present = {t.description for t in list_tickets(db_path=db_path) if t.is_sample}
    with connect(db_path) as conn:
        location_ids = {r["display_name"]: r["location_id"] for r in conn.execute("SELECT display_name,location_id FROM campus_locations")}
    created = 0
    for _, text, location in SAMPLE_REPORTS:
        if text in present:
            continue
        create_ticket(fallback_analysis(text), text, location, "fallback", is_sample=True,
                      db_path=db_path, location_id=location_ids.get(location))
        created += 1
    return created

if __name__ == "__main__":
    import sys
    init_db()
    if "--demo-accounts" in sys.argv:  # known passwords: for local demos ONLY, never on a public deployment
        from auth_service import AuthError, create_staff, create_worker, register_student, DEMO_WORKER_ACCOUNTS, DEMO_PASSWORD
        for role, name, email, pw, occupation in DEMO:
            try:
                if role == "staff":
                    create_staff(name, email, pw, is_demo=True)
                elif role == "worker":
                    create_worker(name, email, pw, occupation, is_demo=True)
                else:
                    from auth_service import _create
                    _create(name, email, pw, "student", is_demo=True)
                print(f"Demo {role}: {email} / {pw}")
            except AuthError:
                print(f"Demo {role} {email} already exists.")
        for name, email, occupation in DEMO_WORKER_ACCOUNTS:
            try:
                create_worker(name, email, DEMO_PASSWORD, occupation, is_demo=True)
                print(f"Demo worker ({occupation}): {email} / {DEMO_PASSWORD}")
            except AuthError:
                print(f"Demo worker {email} already exists.")
        print("WARNING: demo accounts use published passwords. Do not use them on a shared deployment.")
    if list_tickets():
        print("Database already has tickets; not seeding.")
    else:
        print(f"Seeded {seed_sample_tickets()} sample tickets.")
