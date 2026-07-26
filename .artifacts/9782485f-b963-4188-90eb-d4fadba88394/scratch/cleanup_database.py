
import sys
import os
sys.path.append(os.getcwd())

from core import database as db
from core.config import set_active_profile, list_profiles
from core.scraping import is_valid_email

def cleanup_profile(profile_name):
    print(f"\n--- Cleaning up profile: {profile_name} ---")
    set_active_profile(profile_name)

    # 1. Get all leads
    leads = db.get_leads()
    print(f"Total leads: {len(leads)}")

    invalid_count = 0

    # 2. Check each lead using is_valid_email
    for lead in leads:
        lead_id, firma, kontakt, email = lead[0], lead[1], lead[2], lead[3]
        if not email or not is_valid_email(email):
            print(f"  [INVALID REGEX] Marking as invalid: {email}")
            db.mark_invalid(email)
            invalid_count += 1
            continue

        # 3. Check for previous hard failures in 'wysylki' table
        with db.get_connection_context() as conn:
            # Find if this email ever had a hard failure (MX or invalid)
            failure = conn.execute(
                "SELECT blad FROM wysylki WHERE email=? AND (blad LIKE '%MX%' OR blad LIKE '%Nieprawidłowy%')",
                (email,)
            ).fetchone()

            if failure:
                print(f"  [PREVIOUS FAILURE] Marking as invalid: {email} (Error: {failure[0]})")
                db.mark_invalid(email)
                invalid_count += 1

    print(f"Finished. Marked {invalid_count} leads as 'błędny'.")

if __name__ == "__main__":
    profiles = list_profiles()
    for p in profiles:
        cleanup_profile(p)
    print("\nGLOBAL CLEANUP COMPLETE!")
