# Zero Amount (invalid)
def test_base_amount_is_zero_invalid():
    # Arrange
    amount = 0.00

    # Act & Assert
    with pytest.raises(ValueError, match="Amount må IKKE være 0"):
        PlannedTransactionsBase(amount=amount)


# Near-Zero Amount (Floating Point Handling) (invalid)
def test_base_amount_near_zero_invalid():
    # Arrange
    amount = 0.0000001

    # Act & Assert
    with pytest.raises(ValueError, match="Amount må IKKE være 0"):
        PlannedTransactionsBase(amount=amount)


# Lower Boundary: -0.01 (valid)
def test_base_amount_negative_boundary_valid():
    # Arrange
    amount = -0.01

    # Act
    txn = PlannedTransactionsBase(amount=amount)

    # Assert
    assert txn.amount == amount


# Amount Rounding Check
def test_base_amount_rounding():
    # Arrange
    input_amount = 123.456
    expected_amount = 123.46

    # Act
    txn = PlannedTransactionsBase(amount=input_amount)

    # Assert
    assert txn.amount == expected_amount


# -------------------------
# Planned Date Validation
# -------------------------

# Past Date (invalid)
def test_base_planned_date_past_invalid():
    # Arrange
    past_date = date.today() - timedelta(days=1)

    # Act & Assert
    with pytest.raises(ValueError, match="Planned date må ikke være i fortiden"):
        PlannedTransactionsBase(amount=VALID_AMOUNT, planned_date=past_date)


# Today's Date (valid)
def test_base_planned_date_today_valid():
    # Arrange
    today = date.today()

    # Act
    txn = PlannedTransactionsBase(amount=VALID_AMOUNT, planned_date=today)

    # Assert
    assert txn.planned_date == today


# Future Date (valid)
def test_base_planned_date_future_valid():
    # Arrange
    future_date = date.today() + timedelta(days=1)

    # Act
    txn = PlannedTransactionsBase(amount=VALID_AMOUNT, planned_date=future_date)

    # Assert
    assert txn.planned_date == future_date


# -------------------------
# Repeat Interval Validation
# -------------------------

# Weekly is valid
def test_base_repeat_interval_weekly_valid():
    # Arrange
    interval = "weekly"

    # Act
    txn = PlannedTransactionsBase(amount=VALID_AMOUNT, repeat_interval=interval)

    # Assert
    assert txn.repeat_interval == interval


# Invalid interval
def test_base_repeat_interval_invalid_value():
    # Arrange
    invalid_interval = "yearly"

    # Act & Assert
    with pytest.raises(ValueError, match="Repeat interval må være en af"):
        PlannedTransactionsBase(amount=VALID_AMOUNT, repeat_interval=invalid_interval)


# None is valid
def test_base_repeat_interval_none_valid():
    # Arrange
    interval = None

    # Act
    txn = PlannedTransactionsBase(amount=VALID_AMOUNT, repeat_interval=interval)

    # Assert
    assert txn.repeat_interval is None


# -------------------------
# Name Field Validation
# -------------------------

def test_base_name_max_length_invalid():
    # Arrange
    name = "A" * 46

    # Act & Assert
    with pytest.raises(ValidationError):
        PlannedTransactionsBase(amount=VALID_AMOUNT, name=name)


# -------------------------
# Integration Tests (PlannedTransactionsCreate)
# -------------------------

def test_create_schema_basic_instantiation_valid():
    # Arrange
    amount = VALID_AMOUNT
    name = "Rent"

    # Act
    txn = PlannedTransactionsCreate(amount=amount, name=name)

    # Assert
    assert txn.name == name


def test_create_inheritance_past_date_invalid():
    # Arrange
    past_date = date.today() - timedelta(days=1)

    # Act & Assert
    with pytest.raises(ValueError, match="Planned date må ikke være i fortiden"):
        PlannedTransactionsCreate(amount=VALID_AMOUNT, planned_date=past_date)
