from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase,sessionmaker

SQlALCHEMY_DATABASE_URL="sqlite:///./blog.db"
engine=create_engine(
    SQlALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread":False}
)

SessionLocal=sessionmaker(autocommit=False,autoflush=False,bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    with SessionLocal() as db:
        yield db
    