from sqlalchemy.ext.asyncio import create_async_engine,AsyncSession,async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

SQlALCHEMY_DATABASE_URL="sqlite+aiosqlite:///./blog.db"

engine=create_async_engine(
    SQlALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread":False}
)

AsyncSessionLocal=async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
    )

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
    