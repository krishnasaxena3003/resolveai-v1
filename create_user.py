"""Create an admin, occupation-scoped worker, or student account."""
import getpass
import argparse
import sys
from auth_service import AuthError, create_staff, create_worker, register_student, set_password
from database import init_db
from schemas import DEPARTMENTS

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "reset":  # forgotten staff (or student) password
        init_db()
        pw = getpass.getpass("New password (min 8 characters): ")
        try:
            set_password(sys.argv[2], pw)
            sys.exit("Password updated. Existing sessions were signed out.")
        except AuthError as e:
            sys.exit(str(e))
    parser = argparse.ArgumentParser(description="Create a staff admin, occupation-scoped worker, or student account.")
    parser.add_argument("role", choices=("staff", "worker", "student"))
    parser.add_argument("name", help="Full name")
    parser.add_argument("email")
    parser.add_argument("--department", choices=DEPARTMENTS,
                        help="Staff response team; omit for an all-departments staff admin.")
    parser.add_argument("--occupation", choices=DEPARTMENTS, help="Required occupation/team for worker accounts.")
    parser.add_argument("--phone", help="Worker SMS contact in international format; defaults to DEFAULT_WORKER_PHONE.")
    args = parser.parse_args()
    role, name, email = args.role, args.name, args.email
    if role == "worker" and not args.occupation:
        parser.error("worker accounts require --occupation")
    if role != "staff" and args.department:
        parser.error("--department can only be used for staff accounts")
    if role != "worker" and args.occupation:
        parser.error("--occupation can only be used for worker accounts")
    if role != "worker" and args.phone:
        parser.error("--phone can only be used for worker accounts")
    pw = getpass.getpass("Password (min 8 characters): ")
    if pw != getpass.getpass("Repeat password: "):
        sys.exit("Passwords did not match.")
    init_db()
    try:
        if role == "staff":
            create_staff(name, email, pw, department=args.department)
        elif role == "worker":
            create_worker(name, email, pw, args.occupation, phone=args.phone)
        else:
            register_student(name, email, pw)
        print(f"Created {role} account for {email}.")
    except AuthError as e:
        sys.exit(str(e))
