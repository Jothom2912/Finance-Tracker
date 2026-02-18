# backend/repositories/mysql/account_group_repository.py
"""MySQL implementation of account group repository."""

import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from backend.models.mysql.account_groups import AccountGroups as AGModel
from backend.models.mysql.user import User as UserModel
from backend.repositories.base import IAccountGroupRepository

logger = logging.getLogger(__name__)


class MySQLAccountGroupRepository(IAccountGroupRepository):
    """MySQL implementation of account group repository."""

    def __init__(self, db: Session):
        if db is None:
            raise ValueError("db: Session parameter is required")
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        try:
            groups = self.db.query(AGModel).offset(skip).limit(limit).all()
            return [self._serialize(g) for g in groups]
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af kontogrupper: {e}")

    def get_by_id(self, group_id: int) -> Optional[Dict]:
        try:
            group = (
                self.db.query(AGModel)
                .filter(AGModel.idAccountGroups == group_id)
                .first()
            )
            return self._serialize(group) if group else None
        except Exception as e:
            raise ValueError(f"Fejl ved hentning af kontogruppe: {e}")

    def create(self, group_data: Dict) -> Dict:
        """Create account group. group_data must include 'user_ids' list."""
        try:
            user_ids = group_data.pop("user_ids", [])
            db_group = AGModel(**group_data)

            # Tilknyt brugere
            if user_ids:
                users = (
                    self.db.query(UserModel)
                    .filter(UserModel.idUser.in_(user_ids))
                    .all()
                )
                if len(users) != len(user_ids):
                    raise ValueError("Mindst én bruger ID er ugyldig.")
                db_group.users.extend(users)

            self.db.add(db_group)
            self.db.commit()
            self.db.refresh(db_group)
            return self._serialize(db_group)
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Integritetsfejl ved oprettelse af gruppe.")
        except ValueError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Fejl ved oprettelse af kontogruppe: {e}")

    def update(self, group_id: int, group_data: Dict) -> Optional[Dict]:
        try:
            db_group = (
                self.db.query(AGModel)
                .filter(AGModel.idAccountGroups == group_id)
                .first()
            )
            if not db_group:
                return None

            # Håndter user_ids separat
            user_ids = group_data.pop("user_ids", None)
            if user_ids is not None:
                users = (
                    self.db.query(UserModel)
                    .filter(UserModel.idUser.in_(user_ids))
                    .all()
                )
                if len(users) != len(user_ids):
                    raise ValueError("Mindst én ny bruger ID er ugyldig.")
                db_group.users = users

            for key, value in group_data.items():
                if hasattr(db_group, key):
                    setattr(db_group, key, value)

            self.db.commit()
            self.db.refresh(db_group)
            return self._serialize(db_group)
        except IntegrityError:
            self.db.rollback()
            raise ValueError("Integritetsfejl ved opdatering af gruppe.")
        except ValueError:
            self.db.rollback()
            raise
        except Exception as e:
            self.db.rollback()
            raise ValueError(f"Fejl ved opdatering af kontogruppe: {e}")

    @staticmethod
    def _serialize(group: AGModel) -> Dict:
        """Convert SQLAlchemy model to dict."""
        return {
            "idAccountGroups": group.idAccountGroups,
            "name": group.name,
            "max_users": getattr(group, "max_users", 20),
            "users": [
                {"idUser": u.idUser, "username": u.username}
                for u in group.users
            ],
        }
