from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.application.dto import (
    EMAIL_MAX,
    PASSWORD_MAX,
    PASSWORD_MIN,
    USERNAME_MAX,
    USERNAME_MIN,
    RegisterDTO,
)


class TestUsernameValidation:
    def test_at_min_boundary_valid(self) -> None:
        dto = RegisterDTO(
            username="a" * USERNAME_MIN,
            email="test@example.com",
            password="p" * PASSWORD_MIN,
        )
        assert len(dto.username) == USERNAME_MIN

    def test_below_min_boundary_invalid(self) -> None:
        with pytest.raises(ValidationError):
            RegisterDTO(
                username="a" * (USERNAME_MIN - 1),
                email="test@example.com",
                password="p" * PASSWORD_MIN,
            )

    def test_at_max_boundary_valid(self) -> None:
        dto = RegisterDTO(
            username="a" * USERNAME_MAX,
            email="test@example.com",
            password="p" * PASSWORD_MIN,
        )
        assert len(dto.username) == USERNAME_MAX

    def test_above_max_boundary_invalid(self) -> None:
        with pytest.raises(ValidationError):
            RegisterDTO(
                username="a" * (USERNAME_MAX + 1),
                email="test@example.com",
                password="p" * PASSWORD_MIN,
            )


class TestEmailValidation:
    def test_valid_format(self) -> None:
        dto = RegisterDTO(
            username="alice",
            email="alice@example.com",
            password="p" * PASSWORD_MIN,
        )
        assert dto.email == "alice@example.com"

    def test_invalid_format(self) -> None:
        with pytest.raises(ValidationError):
            RegisterDTO(
                username="alice",
                email="not-an-email",
                password="p" * PASSWORD_MIN,
            )


class TestPasswordValidation:
    def test_at_min_boundary_valid(self) -> None:
        dto = RegisterDTO(
            username="alice",
            email="test@example.com",
            password="p" * PASSWORD_MIN,
        )
        assert len(dto.password) == PASSWORD_MIN

    def test_below_min_boundary_invalid(self) -> None:
        with pytest.raises(ValidationError):
            RegisterDTO(
                username="alice",
                email="test@example.com",
                password="p" * (PASSWORD_MIN - 1),
            )

    def test_at_max_boundary_valid(self) -> None:
        dto = RegisterDTO(
            username="alice",
            email="test@example.com",
            password="p" * PASSWORD_MAX,
        )
        assert len(dto.password) == PASSWORD_MAX

    def test_above_max_boundary_invalid(self) -> None:
        with pytest.raises(ValidationError):
            RegisterDTO(
                username="alice",
                email="test@example.com",
                password="p" * (PASSWORD_MAX + 1),
            )
