# ❌ ✅ Common BVA Mistakes & Best Practices

## Mistake 1: Putting BVA in Models

### ❌ FORKERT - Model med validering:
```python
# backend/models/category.py
from sqlalchemy import CheckConstraint

class Category(Base):
    __tablename__ = "Category"
    
    idCategory = Column(Integer, primary_key=True)
    name = Column(String(45), nullable=False)
    type = Column(String(45), nullable=False)
    
    # ❌ FORKERT: Validering i model
    @validates('type')
    def validate_type(self, key, value):
        if value not in ["income", "expense"]:
            raise ValueError("Invalid type")
        return value
```

**Hvorfor det er dårligt:**
- ❌ Valideres kun EFTER at data er i databasen
- ❌ Brugeren får ingen feedback før upload
- ❌ Svært at teste
- ❌ Model bliver kompleks og stor

### ✅ RIGTIGT - Model uden validering:
```python
# backend/models/category.py

class Category(Base):
    __tablename__ = "Category"
    
    idCategory = Column(Integer, primary_key=True)
    name = Column(String(45), nullable=False)
    type = Column(String(45), nullable=False)
    
    def __repr__(self):
        return f"<Category(name='{self.name}', type='{self.type}')>"
```

**Hvorfor det er godt:**
- ✅ Model er simpel og fokuseret på data representation
- ✅ Validering sker før model-oprettelse
- ✅ Nemt at teste
- ✅ Separation of concerns

---

## Mistake 2: Putting BVA in Services

### ❌ FORKERT - Service med input validering:
```python
# backend/services/category_service.py

def create_category(db: Session, name: str, type: str) -> Category:
    # ❌ FORKERT: Gentagende validering
    if not name or len(name) > 30:
        raise ValueError("Name length invalid")
    
    if type not in ["income", "expense"]:
        raise ValueError("Type must be income or expense")
    
    category = Category(name=name, type=type)
    db.add(category)
    db.commit()
    return category
```

**Hvorfor det er dårligt:**
- ❌ Duplikering (validering på to steder)
- ❌ Router kalder service med raw strings (ikke type-sikker)
- ❌ Svært at teste validering
- ❌ Bruger får uventet fejl

### ✅ RIGTIGT - Service kun med kontekst-logik:
```python
# backend/services/category_service.py
from ..schemas.category import CategoryCreate

def create_category(db: Session, category: CategoryCreate) -> Category:
    # ✅ Input er ALLEREDE valideret af Pydantic!
    # category.name er garanteret 1-30 chars
    # category.type er garanteret "income" eller "expense"
    
    # ✅ SERVICE: Kun business logic (FK, duplicates osv)
    existing = db.query(Category).filter(
        Category.name == category.name
    ).first()
    
    if existing:
        raise ValueError("Category with this name already exists")
    
    db_category = Category(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category
```

**Hvorfor det er godt:**
- ✅ Ingen duplikering
- ✅ Router kalder med typed CategoryCreate (sikker)
- ✅ Service fokuserer på business logic
- ✅ Nem at teste (kan bare mock Category)

---

## Mistake 3: Floating Point Equality

### ❌ FORKERT - Direct float comparison:
```python
# test_bva_validation.py

def test_amount():
    amount = BudgetCreate(amount=0.01)
    assert amount.amount == 0.01  # ❌ FORKERT!
    # Can fail due to floating point precision
    # 0.01 might be stored as 0.010000000000000002
```

### ✅ RIGTIGT - Tolerance comparison:
```python
# test_bva_validation.py

def test_amount():
    amount = BudgetCreate(amount=0.01)
    assert abs(amount.amount - 0.01) < 0.001  # ✅ RIGTIGT!
    # Allows for floating point imprecision
```

---

## Mistake 4: Wrong Field Type

### ❌ FORKERT - Using Decimal in Pydantic:
```python
# backend/schemas/budget.py

from decimal import Decimal

class BudgetCreate(BaseModel):
    amount: Decimal = Field(..., ge=0)  # ❌ Problematic
    # Decimal doesn't JSON serialize well
    # Can cause issues in FastAPI responses
```

### ✅ RIGTIGT - Using float in Pydantic, Decimal in DB:
```python
# backend/schemas/budget.py
# backend/models/budget.py

# Schema: Use float (JSON-safe)
class BudgetCreate(BaseModel):
    amount: float = Field(..., ge=0)  # ✅ JSON-serializable

# Model: Use DECIMAL (database precision)
class Budget(Base):
    amount = Column(DECIMAL(15, 2), nullable=False)  # ✅ Precise storage
```

---

## Mistake 5: Forgetting to Round

### ❌ FORKERT - No rounding:
```python
@field_validator('amount')
@classmethod
def validate_amount(cls, v: float) -> float:
    if v < 0:
        raise ValueError("Amount must be >= 0")
    return v  # ❌ Might be 0.010000000000000002
```

### ✅ RIGTIGT - Round to decimals:
```python
@field_validator('amount')
@classmethod
def validate_amount(cls, v: float) -> float:
    if v < 0:
        raise ValueError("Amount must be >= 0")
    return round(v, 2)  # ✅ Ensures proper precision
```

---

## Mistake 6: Not Testing Boundaries

### ❌ FORKERT - Only testing valid case:
```python
def test_category_name():
    cat = CategoryCreate(name="Food", type="expense")
    assert cat.name == "Food"  # ❌ Only tests middle case
```

### ✅ RIGTIGT - Testing boundaries:
```python
def test_category_name_boundaries():
    # Test boundary: too short
    with pytest.raises(ValidationError):
        CategoryCreate(name="", type="expense")
    
    # Test boundary: minimum valid
    valid = CategoryCreate(name="A", type="expense")
    assert len(valid.name) == 1
    
    # Test boundary: maximum valid
    valid = CategoryCreate(name="A" * 30, type="expense")
    assert len(valid.name) == 30
    
    # Test boundary: too long
    with pytest.raises(ValidationError):
        CategoryCreate(name="A" * 31, type="expense")
```

---

## Mistake 7: Not Validating Cross-Field Logic

### ❌ FORKERT - Only validating individual fields:
```python
class GoalCreate(BaseModel):
    target_amount: float = Field(..., ge=0)
    current_amount: float = Field(..., ge=0)
    
    # ❌ No validation that current <= target!
    # User could create goal with current=101, target=100
```

### ✅ RIGTIGT - Cross-field validation:
```python
class GoalCreate(BaseModel):
    target_amount: float = Field(..., ge=0)
    current_amount: float = Field(..., ge=0)
    
    @field_validator('current_amount')
    @classmethod
    def validate_current_vs_target(cls, v: float, info) -> float:
        if 'target_amount' in info.data:
            target = info.data['target_amount']
            if v > target:  # ✅ Checks relationship
                raise ValueError("current cannot exceed target")
        return v
```

---

## Mistake 8: Wrong Error Type

### ❌ FORKERT - Using wrong exception:
```python
# Router receives wrong exception type
def create_goal(goal: GoalCreate):
    try:
        return goal_service.create_goal(db, goal)
    except ValidationError:  # ❌ Wrong exception type!
        # Schema validation already happened!
        # Service throws ValueError, not ValidationError
```

### ✅ RIGTIGT - Proper exception handling:
```python
from fastapi import HTTPException
from pydantic import ValidationError

# Schema throws ValidationError
# Router automatically handles (422 response)

# Service throws ValueError
# Router should catch and convert to HTTPException
@app.post("/goals/")
async def create_goal(goal: GoalCreate):  # ← ValidationError caught by FastAPI
    try:
        return goal_service.create_goal(db, goal)
    except ValueError as e:  # ← Service ValueError
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Mistake 9: Skipping Optional Fields

### ❌ FORKERT - Validating all fields same way:
```python
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)
    type: str
    description: str = Field(..., min_length=1, max_length=200)  # ❌ Should be optional!
```

### ✅ RIGTIGT - Proper optional handling:
```python
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)  # Required
    type: str  # Required
    description: Optional[str] = Field(
        default=None,
        max_length=200
    )  # Optional - can be None or empty
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        # If provided, must not be only whitespace
        if v is not None and v.strip() == "":
            return None
        return v
```

---

## Mistake 10: Inconsistent Boundary Values

### ❌ FORKERT - Boundaries aren't centralized:
```python
# In schemas/category.py
class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)

# In schemas/account.py
class AccountCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=35)  # ❌ Different limit!

# In schemas/user.py
class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, max_length=25)  # ❌ Different limits!
```

### ✅ RIGTIGT - Centralized boundaries:
```python
# validation_boundaries.py
@dataclass
class CategoryBoundaries:
    name_min_length: int = 1
    name_max_length: int = 30

@dataclass
class AccountBoundaries:
    name_min_length: int = 1
    name_max_length: int = 30

# In schemas
from ..validation_boundaries import CATEGORY_BVA, ACCOUNT_BVA

class CategoryCreate(BaseModel):
    name: str = Field(..., 
        min_length=CATEGORY_BVA.name_min_length,
        max_length=CATEGORY_BVA.name_max_length
    )

class AccountCreate(BaseModel):
    name: str = Field(...,
        min_length=ACCOUNT_BVA.name_min_length,
        max_length=ACCOUNT_BVA.name_max_length
    )
```

---

## Quick Reference: What Goes Where?

| Validation Type | Schema? | Service? | Model? |
|-----------------|---------|----------|--------|
| Type checking (str/int/float) | ✅ | ❌ | ❌ |
| Length constraints (min/max) | ✅ | ❌ | ❌ |
| Enum validation (income/expense) | ✅ | ❌ | ❌ |
| Numeric ranges (ge, le) | ✅ | ❌ | ❌ |
| Cross-field logic (current <= target) | ✅ | ❌ | ❌ |
| FK existence (Account exists?) | ❌ | ✅ | ❌ |
| Business rules (duplicate name) | ❌ | ✅ | ❌ |
| Data relationships (back_populates) | ❌ | ❌ | ✅ |
| Cascade rules (delete-orphan) | ❌ | ❌ | ✅ |
| CHECK constraints (DB-level) | ❌ | ❌ | ✅ |

---

## Complete Example: Right Way

```python
# 1. Define boundaries
# validation_boundaries.py
@dataclass
class BudgetBoundaries:
    amount_min: Decimal = Decimal("0.00")
    valid_periods: Tuple[str, ...] = ("weekly", "monthly", "yearly")

# 2. Schema with validation
# schemas/budget.py
from pydantic import BaseModel, Field, field_validator
from ..validation_boundaries import BUDGET_BVA

class BudgetCreate(BaseModel):
    amount: float = Field(..., ge=0, description="Amount >= 0")
    period: str = Field(..., description="weekly/monthly/yearly")
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v):
        return round(v, 2)
    
    @field_validator('period')
    @classmethod
    def validate_period(cls, v):
        if v not in BUDGET_BVA.valid_periods:
            raise ValueError(f"Period must be {BUDGET_BVA.valid_periods}")
        return v

# 3. Model only
# models/budget.py
class Budget(Base):
    __tablename__ = "Budget"
    amount = Column(DECIMAL(15, 2), nullable=False)
    period = Column(String(20), nullable=False)

# 4. Service with business logic
# services/budget_service.py
def create_budget(db: Session, budget: BudgetCreate):
    # amount is already validated and rounded
    # period is already validated
    
    # Check FK existence
    account = db.query(Account).filter(...).first()
    if not account:
        raise ValueError("Account not found")
    
    db_budget = Budget(**budget.model_dump())
    db.add(db_budget)
    db.commit()
    return db_budget

# 5. Tests
# tests/test_bva_validation.py
def test_budget_amount_boundaries():
    # Test -0.01 (invalid)
    with pytest.raises(ValidationError):
        BudgetCreate(amount=-0.01, period="monthly")
    
    # Test 0 (valid)
    valid = BudgetCreate(amount=0.00, period="monthly")
    assert abs(valid.amount - 0.00) < 0.001
    
    # Test 0.01 (valid)
    valid = BudgetCreate(amount=0.01, period="monthly")
    assert abs(valid.amount - 0.01) < 0.001
```

---

## Summary

✅ **DO:**
- Put BVA validation in **Schemas**
- Centralize boundaries in **validation_boundaries.py**
- Use **@field_validator** for complex logic
- Test **boundary values** (min-1, min, max, max+1)
- Handle exceptions at **router level**
- Use **tolerance** for float comparison

❌ **DON'T:**
- Put validation logic in models
- Put input validation in services
- Duplicate validation across layers
- Use direct float equality
- Forget cross-field validation
- Mix business rules with type validation

**Result:** Robust, testable, maintainable code! 🚀
