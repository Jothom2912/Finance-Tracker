from __future__ import annotations

import logging

from app.application.dto import (
    AllocationHistoryEntryResponse,
    GoalBase,
    GoalCreate,
    UnallocatedSurplusEntryResponse,
    UnallocatedSurplusResponse,
)
from app.application.dto import Goal as GoalDTO
from app.application.ports.inbound import IGoalService
from app.application.ports.outbound import IAccountPort, IUnitOfWork
from app.domain.entities import Goal, GoalStatus
from app.domain.exceptions import AccountNotFoundForGoal, NotAccountOwner
from contracts.events.goal import GoalCreatedEvent, GoalDeletedEvent, GoalUpdatedEvent

logger = logging.getLogger(__name__)


class GoalService(IGoalService):
    """Use cases for goals.

    P3-59, om de to ejerskabs-stier i denne klasse: servicen afviser det *samme*
    krydsbruger-forsøg med to forskellige statuskoder, afhængigt af hvilken rute det kom
    ind ad.  Målt i step 1: ``GET /goals`` med et fremmed ``X-Account-ID`` giver **403**,
    ``GET /goals/50`` på et fremmed mål giver **404**.

    Ingen af dem er forkerte — 404 på et fremmed mål er endda den mere lukkede af de to,
    fordi den ikke bekræfter at målet findes.  Men de er *uensartede*, og 404-varianten er
    fuldstændig tavs: en 404 fra "målet findes ikke" og en 404 fra "målet er en andens"
    ser identiske ud både for klienten og i access-loggen.

    Derfor to linjer med hver sin ordlyd — og hver siger hvilken statuskode der fulgte, så
    et fund i loggen kan matches mod access-linjen ved siden af.
    """

    def __init__(self, uow: IUnitOfWork, account_port: IAccountPort) -> None:
        self._uow = uow
        self._account_port = account_port

    async def _verify_ownership(self, account_id: int, user_id: int) -> int:
        owner_id = await self._account_port.get_owner_user_id(account_id)
        if owner_id != user_id:
            logger.warning(
                "Afvist konto-adgang (403): bruger %s forsøgte konto %s (ejet af %s)",
                user_id,
                account_id,
                owner_id,
            )
            raise NotAccountOwner()
        return owner_id

    def _deny_foreign_goal(
        self, operation: str, goal_id: int | None, account_id: int, owner_id: int, user_id: int
    ) -> None:
        """Log at et *eksisterende* mål blev nægtet fordi det tilhører en anden.

        Kaldes de seks steder hvor ``return None``/``return False`` bliver til en 404.  Det
        er hele pointen med linjen: uden den er dette tilfælde ikke til at skelne fra den
        helt almindelige 404 hvor målet aldrig har eksisteret — og kun det ene af dem er
        interessant.  Målet findes IKKE her og der er ikke noget tab; der logges intet.
        """
        logger.warning(
            "Afvist %s af fremmed mål (404): bruger %s forsøgte mål %s på konto %s (ejet af %s)",
            operation,
            user_id,
            goal_id,
            account_id,
            owner_id,
        )

    async def get_goal(self, goal_id: int, user_id: int) -> GoalDTO | None:
        async with self._uow:
            goal = await self._uow.goals.get_by_id(goal_id)
        if not goal:
            return None
        owner_id = await self._account_port.get_owner_user_id(goal.account_id)
        if owner_id != user_id:
            self._deny_foreign_goal("læsning", goal.id, goal.account_id, owner_id, user_id)
            return None
        return self._to_dto(goal)

    async def list_goals(self, account_id: int, user_id: int) -> list[GoalDTO]:
        await self._verify_ownership(account_id, user_id)
        async with self._uow:
            goals = await self._uow.goals.get_all(account_id=account_id)
        return [self._to_dto(goal) for goal in goals]

    async def create_goal(self, data: GoalCreate, user_id: int) -> GoalDTO:
        owner_id = await self._verify_ownership(data.Account_idAccount, user_id)

        if not await self._account_port.exists(data.Account_idAccount):
            raise AccountNotFoundForGoal(data.Account_idAccount)

        goal = Goal(
            id=None,
            name=data.name,
            target_amount=data.target_amount,
            current_amount=data.current_amount,
            target_date=data.target_date,
            status=data.status or "active",
            account_id=data.Account_idAccount,
        )

        async with self._uow:
            created = await self._uow.goals.create(goal)
            await self._uow.outbox.add(
                event=GoalCreatedEvent(
                    goal_id=created.id or 0,
                    user_id=owner_id,
                    name=created.name,
                    target_amount=str(created.target_amount),
                    current_amount=str(created.current_amount),
                    target_date=created.target_date,
                    status=created.status,
                ),
                aggregate_type="goal",
                aggregate_id=str(created.id or 0),
            )
            await self._uow.commit()
        return self._to_dto(created)

    async def update_goal(self, goal_id: int, data: GoalBase, user_id: int) -> GoalDTO | None:
        async with self._uow:
            existing = await self._uow.goals.get_by_id(goal_id)
            if not existing:
                return None
            owner_id = await self._account_port.get_owner_user_id(existing.account_id)
            if owner_id != user_id:
                self._deny_foreign_goal("opdatering", goal_id, existing.account_id, owner_id, user_id)
                return None
            updated = Goal(
                id=goal_id,
                name=data.name,
                target_amount=data.target_amount,
                current_amount=data.current_amount,
                target_date=data.target_date,
                status=data.status,
                account_id=existing.account_id,
            )
            result = await self._uow.goals.update(updated)
            await self._uow.outbox.add(
                event=GoalUpdatedEvent(
                    goal_id=result.id or 0,
                    user_id=owner_id,
                    name=result.name,
                    target_amount=str(result.target_amount),
                    current_amount=str(result.current_amount),
                    target_date=result.target_date,
                    status=result.status,
                ),
                aggregate_type="goal",
                aggregate_id=str(result.id or 0),
            )
            await self._uow.commit()
        return self._to_dto(result)

    async def delete_goal(self, goal_id: int, user_id: int) -> bool:
        async with self._uow:
            existing = await self._uow.goals.get_by_id(goal_id)
            if not existing:
                return False
            owner_id = await self._account_port.get_owner_user_id(existing.account_id)
            if owner_id != user_id:
                self._deny_foreign_goal("sletning", goal_id, existing.account_id, owner_id, user_id)
                return False
            deleted = await self._uow.goals.delete(goal_id)
            if not deleted:
                return False
            await self._uow.outbox.add(
                event=GoalDeletedEvent(goal_id=goal_id, user_id=owner_id),
                aggregate_type="goal",
                aggregate_id=str(goal_id),
            )
            await self._uow.commit()
        return True

    async def set_default_goal(self, goal_id: int, user_id: int) -> GoalDTO | None:
        async with self._uow:
            existing = await self._uow.goals.get_by_id(goal_id)
            if not existing:
                return None
            owner_id = await self._account_port.get_owner_user_id(existing.account_id)
            if owner_id != user_id:
                self._deny_foreign_goal("sæt-default", goal_id, existing.account_id, owner_id, user_id)
                return None
            await self._uow.goals.set_default_savings_goal(goal_id, existing.account_id)
            result = await self._uow.goals.get_by_id(goal_id)
            assert result is not None
            await self._add_goal_updated_event(result, owner_id)
            await self._uow.commit()
        return self._to_dto(result)

    async def clear_default_goal(self, goal_id: int, user_id: int) -> GoalDTO | None:
        async with self._uow:
            existing = await self._uow.goals.get_by_id(goal_id)
            if not existing:
                return None
            owner_id = await self._account_port.get_owner_user_id(existing.account_id)
            if owner_id != user_id:
                self._deny_foreign_goal("ryd-default", goal_id, existing.account_id, owner_id, user_id)
                return None
            await self._uow.goals.clear_default_savings_goal(goal_id)
            result = await self._uow.goals.get_by_id(goal_id)
            assert result is not None
            await self._add_goal_updated_event(result, owner_id)
            await self._uow.commit()
        return self._to_dto(result)

    async def get_allocation_history(self, goal_id: int, user_id: int) -> list[AllocationHistoryEntryResponse] | None:
        async with self._uow:
            goal = await self._uow.goals.get_by_id(goal_id)
            if not goal:
                return None
            owner_id = await self._account_port.get_owner_user_id(goal.account_id)
            if owner_id != user_id:
                self._deny_foreign_goal("historik-opslag", goal_id, goal.account_id, owner_id, user_id)
                return None
            entries = await self._uow.allocations.list_for_goal(goal_id)
        return [AllocationHistoryEntryResponse.model_validate(entry) for entry in entries]

    async def get_unallocated_surplus(self, account_id: int, user_id: int) -> UnallocatedSurplusResponse:
        await self._verify_ownership(account_id, user_id)
        async with self._uow:
            entries = await self._uow.unallocated.list_for_account(account_id)
        return UnallocatedSurplusResponse(
            total=round(sum(entry.amount for entry in entries), 2),
            entries=[UnallocatedSurplusEntryResponse.model_validate(entry) for entry in entries],
        )

    async def _add_goal_updated_event(self, goal: Goal, owner_id: int) -> None:
        await self._uow.outbox.add(
            event=GoalUpdatedEvent(
                goal_id=goal.id or 0,
                user_id=owner_id,
                name=goal.name,
                target_amount=str(goal.target_amount),
                current_amount=str(goal.current_amount),
                target_date=goal.target_date,
                status=goal.status,
            ),
            aggregate_type="goal",
            aggregate_id=str(goal.id or 0),
        )

    def _to_dto(self, goal: Goal) -> GoalDTO:
        return GoalDTO(
            idGoal=goal.id,
            name=goal.name,
            target_amount=goal.target_amount,
            current_amount=goal.current_amount,
            target_date=goal.target_date,
            status=goal.status or GoalStatus.ACTIVE,
            effective_status=goal.effective_status,
            progress_percent=goal.progress_percent,
            Account_idAccount=goal.account_id,
            is_default_savings_goal=goal.is_default_savings_goal,
        )
