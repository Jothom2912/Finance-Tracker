
# BudgetUpdate Tests
# -------------------------

class BudgetUpdate(BaseModel):
    # For updates, all fields are optional
    amount: Optional[float] = None
    budget_date: Optional[date] = None
    Account_idAccount: Optional[int] = None


# Update Schema - All Fields Omitted - VALID
def test_update_all_fields_omitted_valid():
    # Act
    update_data = BudgetUpdate()

    # Assert
    assert update_data.amount is None
    assert update_data.budget_date is None
    assert update_data.Account_idAccount is None


# Update Schema - Partial Update (Only amount provided) - VALID
def test_update_partial_update_valid():
    # Arrange
    input_amount = 500.55

    # Act
    update_data = BudgetUpdate(amount=input_amount)

    # Assert
    assert update_data.amount == input_amount
    assert update_data.budget_date is None
    assert update_data.Account_idAccount is None