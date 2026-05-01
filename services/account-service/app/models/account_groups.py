# app/models/account_groups.py

from .common import (
    Base,
    Column,
    Integer,
    String,
    # IMPORTER NU ASSOCIATIONSTABELLEN DIREKTE FRA COMMON.PY:
    account_group_user_association,
    relationship,
)

# FJERN DEN GAMLE LINJE:
# from .__init__ import ( ... )

class AccountGroups(Base):
    __tablename__ = "AccountGroups"

    idAccountGroups = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=True)
    max_users = Column(Integer, nullable=False, default=20)

    def __repr__(self):
        return f"<AccountGroups(idAccountGroups={self.idAccountGroups}, name='{self.name}')>"




#class AccountGroups(Base):
#    """Kontogruppe model - Bruges til at gruppere konti (f.eks. familiebudget)"""
#
#   __tablename__ = "AccountGroups"
#
#    idAccountGroups = Column(Integer, primary_key=True, autoincrement=True)
#    name = Column(String(45), nullable=True)
#
#    # No FK on junction.User_idUser — explicit joins needed
#    users = relationship(
#        "User",
#        secondary=account_group_user_association,
#        primaryjoin=lambda: (
#            AccountGroups.idAccountGroups == account_group_user_association.c.AccountGroups_idAccountGroups
#        ),
#        secondaryjoin=lambda: account_group_user_association.c.User_idUser == Base.metadata.tables["User"].c.idUser,
#        foreign_keys=[
#            account_group_user_association.c.AccountGroups_idAccountGroups,
#            account_group_user_association.c.User_idUser,
#        ],
#        back_populates="account_groups",
#    )
#
#    def __repr__(self):
#        return f"<AccountGroups(idAccountGroups={self.idAccountGroups}, name='{self.name}')>"
#