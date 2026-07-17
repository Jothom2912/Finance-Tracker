"""RuleService — user-scoped CRUD for categorization rules (F1-02).

Users author KEYWORD rules only; MERCHANT rules are auto-managed by the
feedback loop (F1-03) but surface through the same list/update/delete
endpoints (``is_learned=True``) so the user can inspect and revoke what
the system has learned.  Seed rules (user_id IS NULL) are invisible and
untouchable here — they are migration-managed.

``on_rules_changed(user_id)`` is an optional callback fired after every
mutation; the composition root wires it to the rule-engine provider's
per-user cache invalidation so changes apply instantly in the API
process (the consumer process converges via TTL).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.exc import IntegrityError

from app.application.dto import CreateRuleDTO, RuleResponseDTO, UpdateRuleDTO
from app.application.ports.inbound import IRuleService
from app.application.ports.outbound import IUnitOfWork
from app.domain.entities import CategorizationRule
from app.domain.exceptions import DuplicateRule, RuleNotFound, SubCategoryNotFound
from app.domain.value_objects import PatternType

logger = logging.getLogger(__name__)

USER_RULE_DEFAULT_PRIORITY = 50


class RuleService(IRuleService):
    def __init__(
        self,
        uow: IUnitOfWork,
        on_rules_changed: Callable[[int], None] | None = None,
    ) -> None:
        self._uow = uow
        self._on_rules_changed = on_rules_changed

    async def list_rules(self, user_id: int) -> list[RuleResponseDTO]:
        async with self._uow:
            rules = await self._uow.rules.find_by_user(user_id)
            name_map = await self._taxonomy_name_map()
        return [self._to_response(rule, name_map) for rule in rules]

    async def create_rule(self, user_id: int, dto: CreateRuleDTO) -> RuleResponseDTO:
        pattern_value = dto.pattern_value.strip()

        async with self._uow:
            subcategory = await self._uow.subcategories.find_by_id(dto.subcategory_id)
            if subcategory is None:
                raise SubCategoryNotFound(dto.subcategory_id)

            try:
                rule = await self._uow.rules.create(
                    CategorizationRule(
                        id=None,
                        user_id=user_id,
                        priority=dto.priority,
                        pattern_type=PatternType.KEYWORD,
                        pattern_value=pattern_value,
                        matches_subcategory_id=dto.subcategory_id,
                        active=dto.active,
                    ),
                )
                await self._uow.commit()
            except IntegrityError as exc:
                # uq_rules_user_pattern (migration 007) — same user, same
                # pattern.  Mapped to 409 instead of leaking a 500.
                raise DuplicateRule(pattern_value) from exc
            name_map = await self._taxonomy_name_map()

        self._notify(user_id)
        return self._to_response(rule, name_map)

    async def update_rule(self, user_id: int, rule_id: int, dto: UpdateRuleDTO) -> RuleResponseDTO:
        fields = dto.model_dump(exclude_unset=True)
        if "pattern_value" in fields:
            fields["pattern_value"] = fields["pattern_value"].strip()

        async with self._uow:
            await self._get_owned_rule(rule_id, user_id)

            if fields.get("subcategory_id") is not None:
                subcategory = await self._uow.subcategories.find_by_id(fields["subcategory_id"])
                if subcategory is None:
                    raise SubCategoryNotFound(fields["subcategory_id"])
                fields["matches_subcategory_id"] = fields.pop("subcategory_id")

            try:
                rule = await self._uow.rules.update(rule_id, **fields)
                await self._uow.commit()
            except IntegrityError as exc:
                raise DuplicateRule(fields.get("pattern_value", "")) from exc
            name_map = await self._taxonomy_name_map()

        self._notify(user_id)
        return self._to_response(rule, name_map)

    async def delete_rule(self, user_id: int, rule_id: int) -> None:
        async with self._uow:
            await self._get_owned_rule(rule_id, user_id)
            await self._uow.rules.delete(rule_id)
            await self._uow.commit()

        self._notify(user_id)

    async def _get_owned_rule(self, rule_id: int, user_id: int) -> CategorizationRule:
        """404 for both missing AND foreign/seed rules — ownership must
        not be probeable through the API."""
        rule = await self._uow.rules.find_by_id(rule_id)
        if rule is None or rule.user_id != user_id:
            raise RuleNotFound(rule_id)
        return rule

    async def _taxonomy_name_map(self) -> dict[int, tuple[str, int, str]]:
        """subcategory_id -> (subcategory_name, category_id, category_name)."""
        categories = {c.id: c.name for c in await self._uow.categories.find_all()}
        return {
            sub.id: (sub.name, sub.category_id, categories.get(sub.category_id, ""))
            for sub in await self._uow.subcategories.find_all()
        }

    def _notify(self, user_id: int) -> None:
        if self._on_rules_changed is not None:
            self._on_rules_changed(user_id)

    @staticmethod
    def _to_response(rule: CategorizationRule, name_map: dict[int, tuple[str, int, str]]) -> RuleResponseDTO:
        sub_name, cat_id, cat_name = name_map.get(rule.matches_subcategory_id, ("", None, ""))
        return RuleResponseDTO(
            id=rule.id or 0,
            pattern_type=rule.pattern_type.value,
            pattern_value=rule.pattern_value,
            subcategory_id=rule.matches_subcategory_id,
            subcategory_name=sub_name,
            category_id=cat_id,
            category_name=cat_name,
            priority=rule.priority,
            active=rule.active,
            is_learned=rule.pattern_type == PatternType.MERCHANT,
        )
