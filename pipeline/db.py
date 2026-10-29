import os
from pathlib import Path
from decimal import Decimal
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer,
                        LargeBinary, BigInteger, JSON, String, Text, UniqueConstraint, create_engine, text, event)
from sqlalchemy.types import TypeDecorator
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class MoneyCents(TypeDecorator):
    """Exact two-decimal money stored as integer cents, never SQLite floats."""
    impl = BigInteger
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, float):
            raise ValueError("Money must use Decimal or an exact decimal string")
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0 or amount > Decimal("9999999999999999.99"):
            raise ValueError("Money is outside the supported range")
        cents = amount * 100
        if cents != cents.to_integral_value():
            raise ValueError("Money must have at most two decimal places")
        return int(cents)

    def process_result_value(self, value, dialect):
        return None if value is None else (Decimal(value) / 100).quantize(Decimal("0.01"))


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    submission_key: Mapped[str] = mapped_column(String(64), unique=True)
    file_hash: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(Text)
    content: Mapped[bytes] = mapped_column(LargeBinary)
    profile: Mapped[dict] = mapped_column(JSON)
    config_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[str | None] = mapped_column(String(40))
    error: Mapped[str | None] = mapped_column(Text)
    error_kind: Mapped[str | None] = mapped_column(String(30))
    schema_info: Mapped[dict | None] = mapped_column(JSON)
    __table_args__ = (CheckConstraint("status in ('pending','processing','completed','failed')"),)


class RawRecord(Base):
    __tablename__ = "raw_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True)
    source_line: Mapped[int] = mapped_column(Integer)
    original: Mapped[dict] = mapped_column(JSON)
    mapped: Mapped[dict] = mapped_column(JSON)
    current: Mapped[dict | None] = mapped_column(JSON)
    initial_issues: Mapped[list | None] = mapped_column(JSON)
    validity: Mapped[str | None] = mapped_column(String(20))
    disposition: Mapped[str | None] = mapped_column(String(30))
    outcome: Mapped[str | None] = mapped_column(String(30))
    __table_args__ = (UniqueConstraint("batch_id", "source_line"),
        CheckConstraint("outcome IS NULL OR outcome in ('accepted_valid','accepted_corrected','quarantined','excluded_duplicate')"),)


class Sale(Base):
    __tablename__ = "sales"
    transaction_id: Mapped[str] = mapped_column(String(200), primary_key=True)
    raw_id: Mapped[int] = mapped_column(ForeignKey("raw_records.id"), unique=True)
    customer_id: Mapped[str] = mapped_column(String(200))
    transaction_date: Mapped[datetime] = mapped_column(Date)
    product: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[object] = mapped_column(MoneyCents())
    currency: Mapped[str] = mapped_column(String(3))
    country: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254))
    total_amount: Mapped[object] = mapped_column(MoneyCents())
    normalized: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (CheckConstraint("quantity > 0"), CheckConstraint("unit_price >= 0"),
        CheckConstraint("total_amount >= 0"), CheckConstraint("total_amount = quantity * unit_price"),
        CheckConstraint("typeof(unit_price) = 'integer' AND typeof(total_amount) = 'integer'"),
        CheckConstraint("currency in ('USD','EUR','GBP','INR')"),
        CheckConstraint("country in ('United States','United Kingdom','Germany','France','India')"))


class Quarantine(Base):
    __tablename__ = "quarantine"
    id: Mapped[int] = mapped_column(primary_key=True)
    raw_id: Mapped[int] = mapped_column(ForeignKey("raw_records.id"), index=True)
    values: Mapped[dict] = mapped_column(JSON)
    issues: Mapped[list] = mapped_column(JSON)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Review(Base):
    __tablename__ = "manual_reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    raw_id: Mapped[int] = mapped_column(ForeignKey("raw_records.id"), index=True)
    actor: Mapped[str] = mapped_column(String(200))
    before: Mapped[dict] = mapped_column(JSON)
    submitted: Mapped[dict] = mapped_column(JSON)
    after: Mapped[dict] = mapped_column(JSON)
    issues: Mapped[list] = mapped_column(JSON)
    outcome: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Attempt(Base):
    __tablename__ = "correction_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"), index=True)
    raw_id: Mapped[int] = mapped_column(ForeignKey("raw_records.id"), index=True)
    review_id: Mapped[int | None] = mapped_column(ForeignKey("manual_reviews.id"))
    field: Mapped[str] = mapped_column(String(100))
    original: Mapped[str] = mapped_column(Text)
    proposed: Mapped[str] = mapped_column(Text)
    rule_id: Mapped[str] = mapped_column(String(100))
    rule_version: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(Text)
    applied: Mapped[bool] = mapped_column(Boolean)
    revalidation_ok: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Duplicate(Base):
    __tablename__ = "duplicate_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    raw_id: Mapped[int] = mapped_column(ForeignKey("raw_records.id"), index=True)
    related_raw_id: Mapped[int] = mapped_column(ForeignKey("raw_records.id"))
    kind: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SchemaVersion(Base):
    __tablename__ = "schema_versions"
    version: Mapped[int] = mapped_column(primary_key=True)


def engine(url=None):
    load_dotenv()
    if url is None:
        root = Path(__file__).resolve().parents[1]
        path = Path(os.environ.get("PIPELINE_DB_PATH", "data/pipeline.sqlite3")).expanduser()
        if not path.is_absolute():
            path = root / path
        url = URL.create("sqlite", database=str(path.resolve()))
    url = make_url(url)
    if url.get_backend_name() != "sqlite":
        raise ValueError("This application uses local SQLite storage only")
    if url.database and url.database != ":memory:":
        Path(url.database).resolve().parent.mkdir(parents=True, exist_ok=True)
    db = create_engine(url, connect_args={"timeout": 30, "check_same_thread": False})

    @event.listens_for(db, "connect")
    def configure(connection, record):
        connection.isolation_level = None
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")

    @event.listens_for(db, "begin")
    def begin(connection):
        # Serialize decisions across threads AND independent application processes.
        # Explicit transactions also make SQLite DDL and rollback behavior reliable.
        connection.exec_driver_sql("BEGIN IMMEDIATE")

    return db


def migrate(db):
    """Ordered, transactional migrations. Append migrations for future schema changes."""
    with db.begin() as conn:
        SchemaVersion.__table__.create(conn, checkfirst=True)
        version = conn.execute(text("SELECT coalesce(max(version), 0) FROM schema_versions")).scalar_one()
        if version > 1:
            raise RuntimeError("Database schema is newer than this application")
        if version < 1:
            Base.metadata.create_all(conn)
            conn.execute(SchemaVersion.__table__.insert().values(version=1))


def sessions(db):
    return sessionmaker(db, expire_on_commit=False)
