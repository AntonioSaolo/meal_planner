import uuid
from .extensions import db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (
    Table,
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    ARRAY,
    Integer,
    Sequence,
)

# Association tables
user_groups = Table(
    "user_groups",
    db.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("group_id", UUID(as_uuid=True), ForeignKey("groups.id"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    db.metadata,
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True),
    Column("role_id", UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True),
)


class User(db.Model):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(40), unique=True, nullable=False)
    # Use Text for password_hash to accommodate longer modern hash formats
    password_hash = Column(Text, nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    avatar_url = Column(String(512), nullable=True)
    groups = db.relationship("Group", secondary=user_groups, back_populates="users")
    roles = db.relationship("Role", secondary=user_roles, back_populates="users")


class Role(db.Model):
    __tablename__ = "roles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(30), unique=True, nullable=False)
    privileges = Column(ARRAY(String), nullable=True)
    users = db.relationship("User", secondary=user_roles, back_populates="roles")


class Group(db.Model):
    __tablename__ = "groups"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(30), unique=True, nullable=False)
    users = db.relationship("User", secondary=user_groups, back_populates="groups")


class Type(db.Model):
    __tablename__ = "types"
    # incremental integer index (unique) for easier ordering/searching
    idx = Column(
        Integer, Sequence("types_idx_seq"), nullable=False, unique=True, index=True
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # add an index on name for faster lookups
    name = Column(String(30), unique=True, nullable=False, index=True)


class Meal(db.Model):
    __tablename__ = "meals"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    description = Column(Text, nullable=True)
    antonio = Column(Text, nullable=True)
    annalisa = Column(Text, nullable=True)
    type_id = Column(UUID(as_uuid=True), ForeignKey("types.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = db.relationship("Type")
    user = db.relationship("User")
