from app.db import Base, engine
from app.models import ApiKey

Base.metadata.create_all(engine)
