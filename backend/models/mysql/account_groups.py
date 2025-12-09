# backend/models/account_groups.py

from .common import (
    Base, 
    Column, 
    Integer, 
    String, 
    relationship,
    # IMPORTER NU ASSOCIATIONSTABELLEN DIREKTE FRA COMMON.PY:
    account_group_user_association
)
# FJERN DEN GAMLE LINJE:
# from .__init__ import ( ... )

class AccountGroups(Base):
    """Kontogruppe model - Bruges til at gruppere konti (f.eks. familiebudget)"""
    __tablename__ = "AccountGroups"
    
    idAccountGroups = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=True)
    
    # Relationships
    users = relationship("User", secondary=account_group_user_association, back_populates="account_groups")
    
    def __repr__(self):
        return f"<AccountGroups(idAccountGroups={self.idAccountGroups}, name='{self.name}')>"