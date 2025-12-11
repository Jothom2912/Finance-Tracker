from pydantic import ValidationError, EmailStr
import pytest
import re
from pydantic import ValidationError
from backend.shared.schemas.user import UserBase, UserCreate


# USER_BVA constants are available (min=3, max=20)

VALID_EMAIL = "test@example.com"

# 1. Min Length (N-1) - INVALID (2 chars)
def test_base_username_min_length_below_boundary_invalid():
    # ACT & ASSERT
    with pytest.raises(ValidationError):
        UserBase(username="ab", email=VALID_EMAIL)

# 2. Min Length (N) - VALID (3 chars)
def test_base_username_min_length_at_boundary_valid():
    username = "abc"
    user = UserBase(username=username, email=VALID_EMAIL)
    assert user.username == username

# 3. Max Length (M) - VALID (20 chars)
def test_base_username_max_length_at_boundary_valid():
    username = "a" * 20
    user = UserBase(username=username, email=VALID_EMAIL)
    assert len(user.username) == 20

# 4. Max Length (M+1) - INVALID (21 chars)
def test_base_username_max_length_above_boundary_invalid():
    # ACT & ASSERT
    with pytest.raises(ValidationError):
        UserBase(username="a" * 21, email=VALID_EMAIL)