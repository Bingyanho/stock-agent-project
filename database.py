import os
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker

# 優先讀取雲端環境變數 DATABASE_URL，如果沒有就預設用本地 SQLite
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./quant_agent.db")

# 建立資料庫引擎
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    # SQLite 需要 check_same_thread 參數
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    # 修正某些雲端平台給的舊版 postgres:// 開頭 (SQLAlchemy 只吃 postgresql://)
    if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
        SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # PostgreSQL 不需要 check_same_thread
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==========================================
# 定義資料表
# ==========================================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    cash = Column(Float, default=200000.0)

class Portfolio(Base):
    __tablename__ = "portfolios"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    ticker = Column(String)
    name = Column(String)
    shares = Column(Integer)
    entry_price = Column(Float)
    peak_price = Column(Float)
    buy_fee = Column(Integer)
    entry_date = Column(String)