"""
NPIDE — ORM Models
===================
Mirror of schema.sql — every table mapped as a SQLAlchemy ORM class.
These are used for type-safe queries and Pydantic schema generation.
"""

from datetime import date, datetime
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Integer, Numeric,
    String, Text, ForeignKey, func
)
from sqlalchemy.orm import relationship
from backend.data_layer.database import Base


class Citizen(Base):
    __tablename__ = "citizens"

    citizen_id  = Column(Integer, primary_key=True, autoincrement=True)
    full_name   = Column(String(100), nullable=False)
    age         = Column(Integer, nullable=False)
    income      = Column(Integer, nullable=False)          # annual INR
    location    = Column(String(100), nullable=False)      # state
    occupation  = Column(String(100), nullable=False)
    gender      = Column(String(20))
    phone       = Column(String(15))
    created_at  = Column(DateTime, default=func.now())

    applications = relationship("Application", back_populates="citizen")
    grievances   = relationship("Grievance",   back_populates="citizen")


class Scheme(Base):
    __tablename__ = "schemes"

    scheme_id           = Column(Integer, primary_key=True, autoincrement=True)
    scheme_name         = Column(String(200), nullable=False)
    description         = Column(Text)
    min_income          = Column(Integer, default=0)
    max_income          = Column(Integer, default=999999999)
    eligible_gender     = Column(String(20), default="All")
    eligible_location   = Column(String(100), default="All")
    eligible_occupation = Column(String(100), default="All")
    min_age             = Column(Integer, default=0)
    max_age             = Column(Integer, default=120)
    benefit_amount      = Column(Integer, nullable=True)
    is_active           = Column(Boolean, default=True)
    created_at          = Column(DateTime, default=func.now())

    applications = relationship("Application",   back_populates="scheme")
    grievances   = relationship("Grievance",     back_populates="scheme")
    analytics    = relationship("PolicyAnalytics", back_populates="scheme", uselist=False)


class Application(Base):
    __tablename__ = "applications"

    app_id      = Column(Integer, primary_key=True, autoincrement=True)
    citizen_id  = Column(Integer, ForeignKey("citizens.citizen_id", ondelete="CASCADE"), nullable=False)
    scheme_id   = Column(Integer, ForeignKey("schemes.scheme_id",  ondelete="CASCADE"), nullable=False)
    status      = Column(String(50), default="pending")   # pending | approved | rejected
    applied_on  = Column(Date, default=func.current_date())
    resolved_on = Column(Date, nullable=True)
    remarks     = Column(Text)
    created_at  = Column(DateTime, default=func.now())

    citizen = relationship("Citizen", back_populates="applications")
    scheme  = relationship("Scheme",  back_populates="applications")


class Grievance(Base):
    __tablename__ = "grievances"

    grievance_id = Column(Integer, primary_key=True, autoincrement=True)
    citizen_id   = Column(Integer, ForeignKey("citizens.citizen_id", ondelete="SET NULL"), nullable=True)
    scheme_id    = Column(Integer, ForeignKey("schemes.scheme_id",   ondelete="SET NULL"), nullable=True)
    location     = Column(String(100), nullable=False)
    category     = Column(String(100))   # delay | corruption | wrong rejection | no awareness
    description  = Column(Text)
    severity     = Column(String(20), default="medium")  # low | medium | high
    status       = Column(String(50), default="open")    # open | in_progress | resolved
    filed_on     = Column(Date, default=func.current_date())
    resolved_on  = Column(Date, nullable=True)
    created_at   = Column(DateTime, default=func.now())

    citizen = relationship("Citizen", back_populates="grievances")
    scheme  = relationship("Scheme",  back_populates="grievances")


class PolicyAnalytics(Base):
    __tablename__ = "policy_analytics"

    analytics_id    = Column(Integer, primary_key=True, autoincrement=True)
    scheme_id       = Column(Integer, ForeignKey("schemes.scheme_id", ondelete="CASCADE"), nullable=False)
    total_eligible  = Column(Integer, default=0)
    total_applied   = Column(Integer, default=0)
    total_approved  = Column(Integer, default=0)
    efficiency_score= Column(Numeric(5, 2))
    # gap_count is a GENERATED column in PG; read-only from ORM
    computed_at     = Column(DateTime, default=func.now())

    scheme = relationship("Scheme", back_populates="analytics")
