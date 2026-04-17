import os
from dotenv import load_dotenv

load_dotenv()

from user_db import create_user, does_user_exist, User, SessionLocal

def test_db():
    print("Testing user_db.py functionality...")
    
    # Check if a random user exists
    test_google_id = "test_google_id_12345"
    print(f"User {test_google_id} exists initially?", does_user_exist(test_google_id))
    
    # Create the user
    print(f"Creating user {test_google_id}...")
    success = create_user(
        google_id=test_google_id,
        email="test@example.com",
        first_name="Test",
        last_name="User"
    )
    print("User creation successful?", success)
    
    # Check if the user exists now
    print(f"User {test_google_id} exists now?", does_user_exist(test_google_id))
    
    # Try to create the same user again
    print("Trying to create the same user again...")
    success_again = create_user(
        google_id=test_google_id,
        email="test@example.com",
        first_name="Test",
        last_name="User"
    )
    print("Second user creation successful (should be False)?", success_again)
    
    # Cleanup (Optional, just to keep DB clean for next runs)
    print("Cleaning up test user...")
    with SessionLocal() as session:
        user = session.query(User).filter(User.google_id == test_google_id).first()
        if user:
            session.delete(user)
            session.commit()
    print("Test finished successfully.")

if __name__ == "__main__":
    test_db()
