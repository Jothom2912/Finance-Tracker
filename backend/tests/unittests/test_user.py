import pytest
from pydantic import ValidationError
from backend.shared.schemas.user import UserBase, UserCreate


# -------------------------
# Helper Constants
# -------------------------

VALID_EMAIL = "test@example.com"
VALID_USERNAME = "validuser"
MIN_PASSWORD_LENGTH = 8  # From USER_BVA


# -------------------------
# UserBase — Username BVA
# -------------------------

# Min Length (N-1) - INVALID (2 chars)
def test_base_username_min_length_below_boundary_invalid():
    # Arrange
    username = "ab"

    # Act & Assert
    with pytest.raises(ValidationError):
        UserBase(username=username, email=VALID_EMAIL)


# Min Length (N) - VALID (3 chars)
def test_base_username_min_length_at_boundary_valid():
    # Arrange
    username = "abc"

    # Act
    user = UserBase(username=username, email=VALID_EMAIL)

    # Assert
    assert user.username == username


# Max Length (M) - VALID (20 chars)
def test_base_username_max_length_at_boundary_valid():
    # Arrange
    username = "a" * 20

    # Act
    user = UserBase(username=username, email=VALID_EMAIL)

    # Assert
    assert len(user.username) == 20


# Max Length (M+1) - INVALID (21 chars)
def test_base_username_max_length_above_boundary_invalid():
    # Arrange
    username = "a" * 21

    # Act & Assert
    with pytest.raises(ValidationError):
        UserBase(username=username, email=VALID_EMAIL)


# -------------------------
# UserBase — Username Format Validation
# -------------------------

# Invalid Characters (contains space)
def test_base_username_format_invalid_characters():
    # Arrange
    username = "user name"

    # Act & Assert
    with pytest.raises(
        ValueError,
        match="Username må kun indeholde bogstaver, tal og underscore",
    ):
        UserBase(username=username, email=VALID_EMAIL)


# Valid Characters (alphanumeric + underscore)
def test_base_username_format_valid_characters():
    # Arrange
    username = "user_name_123"

    # Act
    user = UserBase(username=username, email=VALID_EMAIL)

    # Assert
    assert user.username == username


# Whitespace Only (INVALID)
def test_base_username_whitespace_only_invalid():
    # Arrange
    username = "   "

    # Act & Assert
    with pytest.raises(
        ValueError,
        match="Username må kun indeholde bogstaver, tal og underscore",
    ):
        UserBase(username=username, email=VALID_EMAIL)


# -------------------------
# UserBase — Email Validation
# -------------------------

# Invalid Email Format
def test_base_email_format_invalid():
    # Arrange
    invalid_email = "invalid-email"

    # Act & Assert
    with pytest.raises(ValidationError):
        UserBase(username="testuser", email=invalid_email)


# Email Normalization to Lowercase
def test_base_email_normalization_valid():
    # Arrange
    input_email = "Test.User@Example.com"
    expected_email = "test.user@example.com"

    # Act
    user = UserBase(username="testuser", email=input_email)

    # Assert
    assert user.email == expected_email


# -------------------------
# UserCreate Tests
# -------------------------

# Missing Password (INVALID)
def test_create_missing_password_invalid():
    # Act & Assert
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(username=VALID_USERNAME, email=VALID_EMAIL)

    # Assert
    assert "password" in str(excinfo.value)


# Password Min Length (N-1) - INVALID
def test_create_password_min_length_below_boundary_invalid():
    # Arrange
    password = "a" * (MIN_PASSWORD_LENGTH - 1)

    # Act & Assert
    with pytest.raises(ValidationError) as excinfo:
        UserCreate(
            username=VALID_USERNAME,
            email=VALID_EMAIL,
            password=password,
        )

    # Assert
    assert "password" in str(excinfo.value)
    assert (
        f"String should have at least {MIN_PASSWORD_LENGTH} characters"
        in str(excinfo.value)
    )


# Password Min Length (N) - VALID
def test_create_password_min_length_at_boundary_valid():
    # Arrange
    password = "a" * MIN_PASSWORD_LENGTH

    # Act
    user = UserCreate(
        username=VALID_USERNAME,
        email=VALID_EMAIL,
        password=password,
    )

    # Assert
    assert len(user.password) == MIN_PASSWORD_LENGTH


# Inheritance Check — Username Max Length
def test_create_inheritance_username_max_length_invalid():
    # Arrange
    username = "a" * 21

    # Act & Assert
    with pytest.raises(ValidationError):
        UserCreate(
            username=username,
            email=VALID_EMAIL,
            password="a" * MIN_PASSWORD_LENGTH,
        )
