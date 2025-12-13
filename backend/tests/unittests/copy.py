


# -------------------------
# GoalCreate Tests
# -------------------------

# Missing Account ID (INVALID)
def test_create_missing_account_id_invalid():
    # Act & Assert
    with pytest.raises(ValidationError) as excinfo:
        GoalCreate(target_amount=VALID_TARGET)

    # Assert
    assert "Account_idAccount" in str(excinfo.value)


# Valid Account ID (VALID)
def test_create_account_id_valid():
    # Arrange
    account_id = REQUIRED_ACCOUNT_ID

    # Act
    goal = GoalCreate(target_amount=VALID_TARGET, Account_idAccount=account_id)

    # Assert
    assert goal.Account_idAccount == account_id


# Inheritance Check - Target Date (INVALID)
def test_create_inheritance_target_date_today_invalid():
    # Arrange
    today = date.today()

    # Act & Assert
    with pytest.raises(ValueError, match="Deadline skal være i fremtiden"):
        GoalCreate(
            target_amount=VALID_TARGET,
            Account_idAccount=REQUIRED_ACCOUNT_ID,
            target_date=today
        )
