from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.sql import func
from database import Base

class Homeowner(Base):
    __tablename__ = "homeowners"

    id = Column(Integer, primary_key=True, index=True)
    house_number = Column(String, unique=True, index=True)
    owner_name = Column(String)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)

class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    homeowner_id = Column(Integer, ForeignKey("homeowners.id"))
    month = Column(Integer)
    year = Column(Integer)
    amount = Column(Float)
    reference_no = Column(String, unique=True)
    status = Column(String, default="PENDING")
    receipt_path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

