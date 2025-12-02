# 🎓 BVA Implementation Step-by-Step Guide

## For ny person på projektet eller hvis du glemmer

---

## Step 1: Forstå grænser (5 min)

**Spørgsmål til hvert felt:**

1. **Hvad er minimumværdi?**
   - Category name: minimum 1 karakter
   - Budget amount: minimum 0.00
   - User age: minimum 0

2. **Hvad er maksimumværdi?**
   - Category name: maksimum 30 karakterer
   - Account saldo: ingen øvre grænse
   - Username: maksimum 20 karakterer

3. **Hvad lige før/efter grænsen?**
   - Category name: "", "A", "A"*30, "A"*31
   - Amount: -0.01, 0, 0.01

4. **Hvilke værdier er ugyldige?**
   - Type: "saving" (kun "income" eller "expense")
   - Period: "quarterly" (kun weekly/monthly/yearly)
   - Email: "invalid@email" (skal have korrekt format)

5. **Hænger det sammen med andre felter?**
   - Goal: current_amount <= target_amount
   - Budget: end_date > start_date
   - Transaction: amount != 0

**Resultat:** Du har liste over alle grænser!

---

## Step 2: Tilføj til validation_boundaries.py (2 min)

```python
# backend/validation_boundaries.py

from dataclasses import dataclass

@dataclass
class YourModelBoundaries:
    # Hvert felt du identificerede i Step 1
    field_min_length: int = 1
    field_max_length: int = 30
    valid_values: Tuple[str, ...] = ("value1", "value2")
    amount_min: Decimal = Decimal("0.00")

# Eksport så det kan importeres
YOUR_MODEL_BVA = YourModelBoundaries()
```

---

## Step 3: Update Schema med validators (10 min)

```python
# backend/schemas/your_model.py

from pydantic import BaseModel, Field, field_validator
from ..validation_boundaries import YOUR_MODEL_BVA

class YourModelCreate(BaseModel):
    # Field 1: Simple constraint
    field_name: str = Field(
        ...,
        min_length=YOUR_MODEL_BVA.field_min_length,
        max_length=YOUR_MODEL_BVA.field_max_length,
        description="Description of field"
    )
    
    # Field 2: Enum validation
    @field_validator('field_enum')
    @classmethod
    def validate_enum_field(cls, v: str) -> str:
        if v not in YOUR_MODEL_BVA.valid_values:
            raise ValueError(
                f"Must be one of {YOUR_MODEL_BVA.valid_values}, got {v}"
            )
        return v
    
    # Field 3: Amount with rounding
    amount: float = Field(..., ge=0)
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Amount must be >= 0")
        return round(v, 2)
```

---

## Step 4: Write tests (15 min)

```python
# backend/tests/test_bva_validation.py

import pytest
from pydantic import ValidationError
from backend.schemas.your_model import YourModelCreate

def test_field_name_boundary_values():
    """BVA: Test min-1, min, max, max+1"""
    
    # Too short (min-1)
    with pytest.raises(ValidationError):
        YourModelCreate(field_name="")
    
    # Minimum valid (min)
    valid = YourModelCreate(field_name="A")
    assert len(valid.field_name) == 1
    
    # Maximum valid (max)
    valid = YourModelCreate(field_name="A" * 30)
    assert len(valid.field_name) == 30
    
    # Too long (max+1)
    with pytest.raises(ValidationError):
        YourModelCreate(field_name="A" * 31)

def test_enum_field_boundary_values():
    """BVA: Only valid enum values accepted"""
    
    # Valid
    valid = YourModelCreate(field_enum="value1")
    assert valid.field_enum == "value1"
    
    # Invalid
    with pytest.raises(ValidationError):
        YourModelCreate(field_enum="invalid_value")

def test_amount_boundary_values():
    """BVA: -0.01 (invalid), 0 (valid), 0.01 (valid)"""
    
    # Invalid: negative
    with pytest.raises(ValidationError):
        YourModelCreate(amount=-0.01)
    
    # Valid: zero
    valid = YourModelCreate(amount=0.00)
    assert abs(valid.amount - 0.00) < 0.001
    
    # Valid: positive
    valid = YourModelCreate(amount=0.01)
    assert abs(valid.amount - 0.01) < 0.001
```

**Run tests:**
```bash
pytest backend/tests/test_bva_validation.py::test_field_name_boundary_values -v
```

---

## Step 5: Update Service (hvis nødvendigt) (5 min)

**Service skal kun håndtere:**
- ✅ FK existence (Account exists?)
- ✅ Business rules (duplicate name?)
- ❌ NOT input validation (Pydantic gør det!)

```python
# backend/services/your_model_service.py

from ..schemas.your_model import YourModelCreate

def create_your_model(db: Session, model: YourModelCreate):
    """
    Input er ALLEREDE valideret af Pydantic!
    - model.field_name: guaranteed 1-30 chars
    - model.amount: guaranteed >= 0
    - model.field_enum: guaranteed valid value
    """
    
    # Only business logic here:
    if db.query(YourModel).filter(
        YourModel.name == model.field_name
    ).first():
        raise ValueError("Name already exists")
    
    # Create and save
    db_model = YourModel(**model.model_dump())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model
```

---

## Step 6: Check Router (1 min)

Router skal bare acceptere det!

```python
# backend/routers/your_model.py

from fastapi import APIRouter, HTTPException
from ..schemas.your_model import YourModelCreate
from ..services import your_model_service

router = APIRouter(prefix="/your_models", tags=["your_models"])

@router.post("/", response_model=dict)
async def create_your_model(model: YourModelCreate, db: Session = Depends(get_db)):
    # ← Pydantic validates here automatically
    # If invalid: returns 422 response
    # If valid: continues to service
    
    try:
        return your_model_service.create_your_model(db, model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Complete Checklist per Model

```
☐ 1. Identify boundaries (min, max, invalid values)
☐ 2. Add to validation_boundaries.py
☐ 3. Import in schema
☐ 4. Add Field constraints (min_length, max_length, ge, etc)
☐ 5. Add @field_validator for complex logic
☐ 6. Add @field_validator for cross-field validation
☐ 7. Write tests for boundary values
  ☐ min-1 (should fail)
  ☐ min (should pass)
  ☐ max (should pass)
  ☐ max+1 (should fail)
  ☐ invalid values (should fail)
☐ 8. Run tests: pytest backend/tests/test_bva_validation.py -v
☐ 9. Update service with FK validation if needed
☐ 10. Verify router handles errors properly
```

---

## Time Estimate

- **Simple model** (basic fields): 20 minutes
- **Complex model** (cross-field logic): 45 minutes
- **Full implementation** (all models): 4-6 hours

---

## Examples You Have

✅ **Complete examples** (copy-paste friendly):
- Category: `backend/schemas/category.py`
- Budget: `backend/schemas/budget.py`
- Goal: `backend/schemas/goal.py`
- Account: `backend/schemas/account.py`
- Transaction: `backend/schemas/transaction.py`

✅ **Test examples:**
- `backend/tests/test_bva_validation.py`

✅ **Boundaries definition:**
- `backend/validation_boundaries.py`

---

## If You Get Stuck

### Problem: "How do I know what the boundaries are?"
**Solution:** Look at your BVA document or database schema
- Check `String(45)` → max length 45
- Check `DECIMAL(15,2)` → precision 15, decimals 2
- Check requirements document

### Problem: "ValidationError in unexpected place"
**Solution:** Remember the order:
1. Pydantic Schema ← Error thrown here (422)
2. Service ← Error thrown here (400/500)
3. Database ← Error thrown here (500)

### Problem: "Floating point comparison fails"
**Solution:** Use tolerance:
```python
assert abs(value - expected) < 0.001  # Not ==
```

### Problem: "Cross-field validation not working"
**Solution:** Make sure you use `info.data`:
```python
@field_validator('field2')
def validate(cls, v, info):
    if 'field1' in info.data:  # ← Check exists first!
        field1_value = info.data['field1']
        if v > field1_value:  # ← Now compare
            raise ValueError("...")
    return v
```

### Problem: "Where should I put this validation?"
**Answer:**
- **Type checking, length, enum?** → Schema
- **FK exists, business rules?** → Service
- **Data relationships, CASCADE?** → Model

---

## Quick Command Reference

```bash
# Run all BVA tests
pytest backend/tests/test_bva_validation.py -v

# Run specific test
pytest backend/tests/test_bva_validation.py::test_category_name_boundary_values -v

# Run with coverage
pytest backend/tests/test_bva_validation.py --cov=backend.schemas

# Run and stop on first failure
pytest backend/tests/test_bva_validation.py -x

# Run with print statements
pytest backend/tests/test_bva_validation.py -v -s
```

---

## Next Models To Do

Priority order:

1. **PlannedTransaction** (amount != 0, date >= today, interval enum)
2. **User** (username/password/email validation)
3. **AccountGroup** (name length, max_users)
4. **AccountGroupUser** (FK validation - service level)

---

## Remember

🎯 **BVA = Boundary Value Analysis**
- Test values RIGHT AT the boundary
- Test one value BEFORE boundary (invalid)
- Test one value AFTER boundary (invalid)
- Test valid values at boundaries

📍 **Três-lag arkitektur:**
- 🟢 **Schema** (Pydantic): Type, length, enum, cross-field
- 🟡 **Service**: FK, business logic
- 🔵 **Model**: Relationships, cascade

✅ **You're doing it right if:**
- Invalid input gets 422 response (Pydantic)
- Valid input checked for FK in service
- Tests cover boundaries
- No validation duplication

**Go forth and validate! 🚀**
