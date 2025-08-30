from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import shortuuid

Base = declarative_base()

def generate_short_code():
    return shortuuid.ShortUUID().random(length=6)

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)
    file_code = Column(String(6), unique=True, default=generate_short_code)
    original_filename = Column(String(255))
    stored_filename = Column(String(255))
    file_size = Column(Integer)
    user_id = Column(Integer)
    upload_date = Column(DateTime, default=datetime.now)
    notify_visits = Column(Boolean, default=True)
    notify_downloads = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

class FileAccess(Base):
    __tablename__ = "file_access"

    id = Column(Integer, primary_key=True)
    file_code = Column(String(6))
    access_type = Column(String(10))
    ip_address = Column(String(45))
    user_agent = Column(Text)
    access_time = Column(DateTime, default=datetime.now)
    country = Column(String(100))
    city = Column(String(100))