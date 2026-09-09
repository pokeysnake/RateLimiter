from app.db import SessionLocal
from app.api_keys import get_config_by_key

session = SessionLocal()

# paste a real raw key you generated via try_create_key.py here
real_key = "yHwHZLPECRQQTrEkBtM1kF-yKdp5mVQzCZhXAv86dVs"

result = get_config_by_key(session, real_key)
if result:
    print(
        f"found: algorithm={result.algorithm}, capacity={result.capacity}, window_seconds={result.window_seconds}"
    )
else:
    print("no match found")

fake_key = "this-key-does-not-exist"
fake_result = get_config_by_key(session, fake_key)
print("fake lookup:", fake_result)
