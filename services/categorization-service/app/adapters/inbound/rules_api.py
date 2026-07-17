"""User-defined categorization rules (F1-02).

JWT-authed and strictly user-scoped: users see and manage only their
own rules.  Learned MERCHANT rules (feedback loop, F1-03) surface here
with ``is_learned=true`` so they can be inspected and revoked; seed
rules (user_id IS NULL) never appear.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.application.dto import CreateRuleDTO, RuleResponseDTO, UpdateRuleDTO
from app.application.rule_service import RuleService
from app.auth import get_current_user_id
from app.dependencies import get_rule_service

rules_router = APIRouter(prefix="/api/v1/rules", tags=["rules"])


@rules_router.get("/", response_model=list[RuleResponseDTO])
async def list_rules(
    user_id: int = Depends(get_current_user_id),
    service: RuleService = Depends(get_rule_service),
) -> list[RuleResponseDTO]:
    return await service.list_rules(user_id)


@rules_router.post("/", response_model=RuleResponseDTO, status_code=status.HTTP_201_CREATED)
async def create_rule(
    dto: CreateRuleDTO,
    user_id: int = Depends(get_current_user_id),
    service: RuleService = Depends(get_rule_service),
) -> RuleResponseDTO:
    return await service.create_rule(user_id, dto)


@rules_router.put("/{rule_id}", response_model=RuleResponseDTO)
async def update_rule(
    rule_id: int,
    dto: UpdateRuleDTO,
    user_id: int = Depends(get_current_user_id),
    service: RuleService = Depends(get_rule_service),
) -> RuleResponseDTO:
    return await service.update_rule(user_id, rule_id, dto)


@rules_router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: int,
    user_id: int = Depends(get_current_user_id),
    service: RuleService = Depends(get_rule_service),
) -> None:
    await service.delete_rule(user_id, rule_id)
