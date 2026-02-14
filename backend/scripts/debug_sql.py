from sqlalchemy.schema import CreateTable
from app.database import engine, Base
# Import all models to ensure metadata is populated
from app.models.user import User
from app.models.reading_room import ReadingRoom, Cabin
from app.models.accommodation import Accommodation
from app.models.review import Review

print("Expected SQL for Review table:")
print(CreateTable(Review.__table__).compile(engine))
