from typing import List, Dict, Optional
from backend.database.mysql import SessionLocal
from backend.models.mysql.account_groups import AccountGroups as GroupAccountModel
from backend.repositories.base import IGroupAccountRepository

class MySQGroupAccountRepository(IGroupAccountRepository):
    """MySQL implementation of group account repository."""
    
    def __init__(self, db: SessionLocal = None):
        self.db = db or SessionLocal()
    
    def get_all(self, account_id: Optional[int] = None) -> List[Dict]:
        from sqlalchemy.orm import joinedload
        query = self.db.query(GroupAccountModel).options(
            joinedload(GroupAccountModel.users)
        )
        # AccountGroups doesn't have account_id filter
        group_accounts = query.all()
        return [self._serialize_group_account(ga) for ga in group_accounts]
    
    def get_by_id(self, group_account_id: int) -> Optional[Dict]:
        from sqlalchemy.orm import joinedload
        group_account = self.db.query(GroupAccountModel).options(
            joinedload(GroupAccountModel.users)
        ).filter(GroupAccountModel.idAccountGroups == group_account_id).first()
        return self._serialize_group_account(group_account) if group_account else None
    
    def create(self, group_account_data: Dict) -> Dict:
        from sqlalchemy.orm import joinedload
        group_account = GroupAccountModel(
            name=group_account_data.get("name")
        )
        self.db.add(group_account)
        self.db.commit()
        self.db.refresh(group_account)
        
        # Handle user association if user_ids is provided
        user_ids = group_account_data.get("user_ids")
        if user_ids:
            from backend.models.mysql.user import User as UserModel
            users = self.db.query(UserModel).filter(UserModel.idUser.in_(user_ids)).all()
            if len(users) != len(user_ids):
                raise ValueError("Mindst én bruger ID er ugyldig.")
            group_account.users.extend(users)
            self.db.commit()
            
            # Reload with users
            group_account = self.db.query(GroupAccountModel).options(
                joinedload(GroupAccountModel.users)
            ).filter(GroupAccountModel.idAccountGroups == group_account.idAccountGroups).first()
        
        return self._serialize_group_account(group_account)
    
    def update(self, group_account_id: int, group_account_data: Dict) -> Dict:
        group_account = self.db.query(GroupAccountModel).filter(GroupAccountModel.idAccountGroups == group_account_id).first()
        if not group_account:
            raise ValueError(f"Group account {group_account_id} not found")
        
        if "name" in group_account_data:
            group_account.name = group_account_data["name"]
        
        self.db.commit()
        self.db.refresh(group_account)
        return self._serialize_group_account(group_account)
    
    def delete(self, group_account_id: int) -> bool:
        group_account = self.db.query(GroupAccountModel).filter(GroupAccountModel.idAccountGroups == group_account_id).first()
        if not group_account:
            return False
        self.db.delete(group_account)
        self.db.commit()
        return True
    
    @staticmethod
    def _serialize_group_account(group_account: GroupAccountModel) -> Dict:
        from backend.validation_boundaries import ACCOUNT_GROUP_BVA
        return {
            "idAccountGroups": group_account.idAccountGroups,
            "name": group_account.name,
            "max_users": ACCOUNT_GROUP_BVA.max_users,
            "users": [{"idUser": u.idUser, "username": u.username, "email": u.email} for u in group_account.users] if group_account.users else []
        }