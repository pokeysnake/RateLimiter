from app.db import SessionLocal
from app.api_keys import create_api_key

session = SessionLocal()
raw_key = create_api_key(session, "sliding_window", 5, 10)
print(raw_key)
