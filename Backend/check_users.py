import os
from dotenv import load_dotenv

load_dotenv()

from user_db import User, SessionLocal

def main():
    with SessionLocal() as session:
        users = session.query(User).all()
        if not users:
            print("No users found in the database.")
            return
            
        print(f"Found {len(users)} user(s):")
        print("-" * 50)
        for u in users:
            print(f"Google ID : {u.google_id}")
            print(f"Email     : {u.email}")
            print(f"First Name: {u.first_name}")
            print(f"Last Name : {u.last_name}")
            print("-" * 50)

if __name__ == "__main__":
    main()
