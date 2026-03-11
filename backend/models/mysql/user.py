# backend/models/user.py

from .common import (
    Base, Column, Integer, String, DateTime, func, relationship,
    account_group_user_association 
)

class User(Base):
    """Bruger model — local cache of user data from user-service."""
    __tablename__ = "User"
    
    idUser = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(45), nullable=False, unique=True, index=True)
    password = Column(String(255), nullable=False)
    email = Column(String(45), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # No FK on junction.User_idUser — explicit joins needed
    account_groups = relationship(
        "AccountGroups",
        secondary=account_group_user_association,
        primaryjoin=lambda: User.idUser == account_group_user_association.c.User_idUser,
        secondaryjoin=lambda: account_group_user_association.c.AccountGroups_idAccountGroups == Base.metadata.tables["AccountGroups"].c.idAccountGroups,
        foreign_keys=[
            account_group_user_association.c.User_idUser,
            account_group_user_association.c.AccountGroups_idAccountGroups,
        ],
        back_populates="users",
    )
    
    def __repr__(self):
        return f"<User(idUser={self.idUser}, username='{self.username}')>"