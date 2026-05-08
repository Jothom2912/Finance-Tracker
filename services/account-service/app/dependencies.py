from fastapi import Depends
from sqlalchemy.orm import Session

from app.adapters.outbound.outbox_repository import SyncOutboxRepository
from app.adapters.outbound.postgresql_account_group_repository import MySQLAccountGroupRepository
from app.adapters.outbound.postgresql_account_repository import MySQLAccountRepository
from app.adapters.outbound.user_adapter import UserServiceAdapter
from app.application.service import AccountService
from app.database import get_db


def get_account_service(db: Session = Depends(get_db)) -> AccountService:
    outbox = SyncOutboxRepository(db)
    return AccountService(
        account_repository=MySQLAccountRepository(db),
        account_group_repository=MySQLAccountGroupRepository(db),
        user_port=UserServiceAdapter(),
        outbox=outbox,
        commit_fn=db.commit,
    )