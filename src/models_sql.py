
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, BigInteger, Float, JSON
from sqlalchemy import ForeignKey
from sqlalchemy import LargeBinary
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.dialects.postgresql import ARRAY

DATABASE_URL = "postgresql://job_user:job_pass@pg_job:5432/job_db"

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()


class Job(Base):

    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    job_id = Column(String, nullable=False, unique=True, index=True)  # External ID
    added_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    country = Column(String)   # US
    state = Column(String)     # California
    city = Column(String)      # San Jose
    location = Column(String)  # San Jose, CA

    job_latitude = Column(Float)   # 37.33874
    job_longitude = Column(Float)  # -121.885

    title = Column(String, nullable=False)
    description = Column(Text)
    job_highlights = Column(JSON)
    job_benefits = Column(Text)

    posted_at_utc = Column(DateTime)   # 2025-07-15T00:00:00.000Z
    posted_at_ts = Column(BigInteger)  # 1752537600

    is_remote = Column(Boolean)
    employment_type = Column(ARRAY(String))  # ['FULLTIME']

    job_min_salary = Column(Integer)    # 184,000
    job_max_salary = Column(Integer)    # 266,000
    job_salary_period = Column(String)  # YEAR

    publisher = Column(String)
    is_direct_apply = Column(Boolean)
    apply_link = Column(String)
    apply_options = Column(JSON)
    job_google_link = Column(String)

    is_summarized = Column(Boolean, default=False)
    is_embedded = Column(Boolean, default=False)

    job_summary = Column(Text)

    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    company = relationship("Company", back_populates="jobs")

    embeddings = relationship("JobEmbedding", back_populates="job", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Job title={self.title} company={self.company.name}>"


class Company(Base):

    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)  # Cisco

    logo_url = Column(String)
    website = Column(String)    # https://www.cisco.com

    jobs = relationship("Job", back_populates="company")

    def __repr__(self):
        return f"<Company name={self.name}>"


class JobEmbedding(Base):

    __tablename__ = "job_embeddings"

    id = Column(Integer, primary_key=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)

    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    embedding = Column(ARRAY(Float), nullable=False)

    job = relationship("Job", back_populates="embeddings")

    def __repr__(self):
        return f"<JobEmbedding job_id={self.job_id} chunk_index={self.chunk_index}>"


class Profile(Base):

    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    added_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    my_location = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    filter_data = Column(JSON, nullable=False)

    resume = Column(LargeBinary, nullable=True)

    def __repr__(self):
        return f"<Profile name={self.name} location={self.my_location}>"


def init_db():

    Base.metadata.create_all(engine)
