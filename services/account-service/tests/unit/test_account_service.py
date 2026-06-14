from __future__ import annotations

import pytest
from app.application.dto import AccountBase, AccountCreate, AccountGroupsCreate
from app.application.service import AccountService
from app.domain.entities import Account, AccountGroup, AccountGroupUser
from app.domain.exceptions import InvalidUserInGroup, UserNotFoundForAccount


class FakeAccountRepository:
    def __init__(self) -> None:
        self.accounts: dict[int, Account] = {}
        self.next_id = 1

    def get_by_id(self, account_id: int) -> Account | None:
        return self.accounts.get(account_id)

    def get_all(self, user_id: int) -> list[Account]:
        return [account for account in self.accounts.values() if account.user_id == user_id]

    def create(self, account: Account) -> Account:
        created = Account(
            id=self.next_id,
            name=account.name,
            saldo=account.saldo,
            user_id=account.user_id,
            budget_start_day=account.budget_start_day,
        )
        self.accounts[self.next_id] = created
        self.next_id += 1
        return created

    def update(self, account: Account) -> Account:
        self.accounts[account.id] = account  # type: ignore[index]
        return account


class FakeAccountGroupRepository:
    def __init__(self) -> None:
        self.groups: dict[int, AccountGroup] = {}
        self.next_id = 1

    def get_by_id(self, group_id: int) -> AccountGroup | None:
        return self.groups.get(group_id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[AccountGroup]:
        return list(self.groups.values())[skip : skip + limit]

    def create(self, group: AccountGroup, user_ids: list[int]) -> AccountGroup:
        users = [AccountGroupUser(id=user_id, username=f"user-{user_id}") for user_id in user_ids]
        created = AccountGroup(id=self.next_id, name=group.name, max_users=group.max_users, users=users)
        self.groups[self.next_id] = created
        self.next_id += 1
        return created

    def update(self, group: AccountGroup, user_ids: list[int]) -> AccountGroup:
        users = [AccountGroupUser(id=user_id, username=f"user-{user_id}") for user_id in user_ids]
        updated = AccountGroup(id=group.id, name=group.name, max_users=group.max_users, users=users)
        self.groups[group.id] = updated  # type: ignore[index]
        return updated


class FakeUserPort:
    def __init__(self, existing_user_ids: set[int]) -> None:
        self.existing_user_ids = existing_user_ids

    def exists(self, user_id: int) -> bool:
        return user_id in self.existing_user_ids

    def get_users_by_ids(self, user_ids: list[int]) -> list[tuple[int, str]]:
        return [(user_id, f"user-{user_id}") for user_id in user_ids if user_id in self.existing_user_ids]


class FakeOutbox:
    def __init__(self) -> None:
        self.events: list[dict] = []

    def add(self, **kwargs) -> None:
        self.events.append(kwargs)


def make_service(user_ids: set[int] | None = None, outbox: FakeOutbox | None = None):
    commits = {"count": 0}

    def commit() -> None:
        commits["count"] += 1

    service = AccountService(
        account_repository=FakeAccountRepository(),
        account_group_repository=FakeAccountGroupRepository(),
        user_port=FakeUserPort(user_ids or {1}),
        outbox=outbox,
        commit_fn=commit,
    )
    return service, commits


def test_create_account_requires_existing_user() -> None:
    service, _ = make_service(user_ids={1})

    with pytest.raises(UserNotFoundForAccount):
        service.create_account(AccountCreate(name="Savings", saldo=100, User_idUser=99, budget_start_day=1))


def test_create_account_persists_data_and_emits_outbox_event() -> None:
    outbox = FakeOutbox()
    service, commits = make_service(user_ids={1}, outbox=outbox)

    created = service.create_account(AccountCreate(name="Budget", saldo=250.5, User_idUser=1, budget_start_day=15))

    assert created.idAccount == 1
    assert created.name == "Budget"
    assert created.saldo == 250.5
    assert created.User_idUser == 1
    assert created.budget_start_day == 15
    assert commits["count"] == 1
    assert outbox.events[0]["event_type"] == "account.created"
    assert outbox.events[0]["payload"]["account_id"] == 1


def test_update_account_keeps_original_owner() -> None:
    service, _ = make_service(user_ids={1})
    created = service.create_account(AccountCreate(name="Old", saldo=10, User_idUser=1, budget_start_day=1))

    updated = service.update_account(
        created.idAccount,
        AccountBase(name="New", saldo=20, budget_start_day=20),
    )

    assert updated is not None
    assert updated.name == "New"
    assert updated.saldo == 20
    assert updated.User_idUser == 1
    assert updated.budget_start_day == 20


def test_create_group_rejects_unknown_users() -> None:
    service, _ = make_service(user_ids={1})

    with pytest.raises(InvalidUserInGroup):
        service.create_group(AccountGroupsCreate(name="Family", max_users=5, user_ids=[1, 2]))


def test_account_entity_clamps_budget_start_day_to_valid_range() -> None:
    assert Account(id=None, name="Low", saldo=0, user_id=1, budget_start_day=-10).budget_start_day == 1
    assert Account(id=None, name="High", saldo=0, user_id=1, budget_start_day=99).budget_start_day == 28
