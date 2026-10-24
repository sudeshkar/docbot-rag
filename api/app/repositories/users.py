from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email.strip().lower()))

    def add(self, email: str, password_hash: str) -> User:
        user = User(email=email.strip().lower(), password_hash=password_hash)
        self.db.add(user)
        self.db.flush()
        return user
