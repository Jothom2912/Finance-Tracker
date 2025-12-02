# 🚀 BVA Implementation - Quick Start

## 📖 Start Her!

Du har implementeret Boundary Value Analysis (BVA) validering på alle dine models. Her er hvordan du bruger det.

---

## 1️⃣ Understand the Architecture

**Din validering sker på 3 lag:**

```
┌─────────────────────────────────────────────────────────────┐
│ USER SENDS JSON DATA                                        │
└──────────────────────┬──────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────┐
│ PYDANTIC SCHEMA (validation_boundaries.py)  ⭐⭐⭐          │
│ ✅ Checks min/max length                                   │
│ ✅ Validates numeric ranges                                │
│ ✅ Checks enums                                            │
│ ✅ Validates dates                                         │
│ ✅ Cross-field validation                                  │
│ If error → return 422 Validation Error immediately         │
└──────────────────────┬──────────────────────────────────────┘
                       ↓ (if valid)
┌─────────────────────────────────────────────────────────────┐
│ SERVICE LAYER (business logic)                              │
│ ✅ Check if foreign keys exist                             │
│ ✅ Apply business rules                                    │
│ If error → return 400 Bad Request                          │
└──────────────────────┬──────────────────────────────────────┘
                       ↓ (if valid)
┌─────────────────────────────────────────────────────────────┐
│ DATABASE (final safety)                                      │
│ ✅ INSERT/UPDATE data                                       │
│ If error → return 500 Server Error (should be rare!)       │
└─────────────────────────────────────────────────────────────┘
```

**Key**: 90% af validering sker i Pydantic! 🎯

---

## 2️⃣ Where BVA is Defined

**File: `backend/validation_boundaries.py`**

Dette er den centrale lokation hvor alle grænseværdier defineres:

```python
@dataclass
class CategoryBoundaries:
    name_min_length: int = 1
    name_max_length: int = 30
    valid_types: Tuple[str, ...] = ("income", "expense")

@dataclass
class UserBoundaries:
    username_min_length: int = 3
    username_max_length: int = 20
    password_min_length: int = 8
```

**Fordele:**
- ✅ Enkelt sted at ændre constraints
- ✅ Reusable i tests
- ✅ Dokumentation samlet

---

## 3️⃣ How Validation Works

### **Example 1: Simple Constraint (Category name)**

```python
# backend/schemas/category.py
class CategoryBase(BaseModel):
    name: str = Field(
        ...,
        min_length=CATEGORY_BVA.name_min_length,  # = 1
        max_length=CATEGORY_BVA.name_max_length,  # = 30
        description="Category name (1-30 characters)"
    )
```

**Testing:**
```python
# ✅ VALID - 1 character
valid = CategoryCreate(name="A", type="income")

# ❌ INVALID - 0 characters (empty)
with pytest.raises(ValidationError):
    CategoryCreate(name="", type="income")

# ❌ INVALID - 31 characters
with pytest.raises(ValidationError):
    CategoryCreate(name="A"*31, type="income")
```

---

### **Example 2: Custom Validation (Budget period)**

```python
# backend/schemas/budget.py
class BudgetBase(BaseModel):
    period: str = Field(...)
    
    @field_validator('period')
    @classmethod
    def validate_period(cls, v: str) -> str:
        """BVA: Period må være weekly, monthly eller yearly"""
        if v not in BUDGET_BVA.valid_periods:
            raise ValueError(f"Period må være en af {BUDGET_BVA.valid_periods}")
        return v
```

**Testing:**
```python
# ✅ VALID
valid = BudgetCreate(..., period="monthly")

# ❌ INVALID
with pytest.raises(ValidationError):
    BudgetCreate(..., period="quarterly")
```

---

### **Example 3: Cross-field Validation (Goal)**

```python
# backend/schemas/goal.py
class GoalBase(BaseModel):
    target_amount: float = Field(..., ge=0)
    current_amount: float = Field(..., ge=0)
    
    @field_validator('current_amount')
    @classmethod
    def validate_current_vs_target(cls, v: float, info) -> float:
        """BVA: current_amount må IKKE være > target_amount"""
        if 'target_amount' in info.data:
            target = info.data['target_amount']
            if v > target:
                raise ValueError(
                    f"Current ({v}) kan ikke være > target ({target})"
                )
        return v
```

**Testing:**
```python
# ✅ VALID - current <= target
valid = GoalCreate(target_amount=100, current_amount=100)

# ❌ INVALID - current > target
with pytest.raises(ValidationError):
    GoalCreate(target_amount=100, current_amount=101)
```

---

## 4️⃣ Using in Your Routers

**Before (without validation):**
```python
@router.post("/categories/")
def create_category(data: dict, db: Session = Depends(get_db)):
    # Du skal selv validere!
    if not data.get('name'):
        raise ValueError("Name is required")
    if len(data['name']) > 30:
        raise ValueError("Name too long")
    # ...
```

**After (with BVA):**
```python
from backend.schemas.category import CategoryCreate

@router.post("/categories/")
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    # ✅ Pydantic har allerede valideret!
    # Du får kun kategori hvis den passerer alle checks
    return category_service.create_category(db, category)
```

**What happens:**
1. User sender JSON: `{"name": "", "type": "income"}`
2. Pydantic validerer med `CategoryCreate`
3. ❌ `name` er tomt → FastAPI returner `422 Validation Error` med dansk besked
4. ✅ Service og database bliver aldrig kaldt

---

## 5️⃣ Test Your Validations

### **Run All BVA Tests:**
```bash
cd c:\Users\johan\Documents\finans\ tracker
pytest backend/tests/test_bva_*.py -v
```

### **Run Specific Test:**
```bash
pytest backend/tests/test_bva_validation.py::test_category_name_boundary_values -v
```

### **Expected Output:**
```
test_bva_validation.py::test_category_name_boundary_values PASSED
test_bva_validation.py::test_budget_amount_boundary_values PASSED
test_bva_additional_models.py::test_user_username_boundary_values PASSED
...
================ 30 passed in 2.34s ================
```

---

## 6️⃣ Common Tasks

### **Task: Add new validation rule**

**Scenario:** Du vil validere at kategori-navn ikke starter med tal

**Step 1:** Opdater `validation_boundaries.py` hvis nødvendigt (ikke nødvendigt her)

**Step 2:** Tilføj validator i schema:
```python
@field_validator('name')
@classmethod
def validate_name_not_starting_with_digit(cls, v: str) -> str:
    if v[0].isdigit():
        raise ValueError("Category name cannot start with a digit")
    return v
```

**Step 3:** Skriv test:
```python
def test_category_name_not_starting_with_digit():
    # ❌ INVALID
    with pytest.raises(ValidationError):
        CategoryCreate(name="1Category", type="income")
    
    # ✅ VALID
    valid = CategoryCreate(name="Category1", type="income")
```

---

### **Task: Change a boundary value**

**Scenario:** Du vil ændre max username fra 20 til 25 tegn

**Step 1:** Opdater `validation_boundaries.py`:
```python
@dataclass
class UserBoundaries:
    username_max_length: int = 25  # ← ændret fra 20
```

**Step 2:** Opdater test i `test_bva_additional_models.py`:
```python
# 25 chars - VALID (ny grænse)
valid = UserCreate(username="a" * 25, ...)
assert len(valid.username) == 25

# 26 chars - INVALID
with pytest.raises(ValidationError):
    UserCreate(username="a" * 26, ...)
```

**Step 3:** Run tests for at sikre ingen bryder:
```bash
pytest backend/tests/test_bva_additional_models.py::test_user_username_boundary_values -v
```

---

### **Task: Add validation to new field**

**Scenario:** Du tilføjer `phone_number` til User

**Step 1:** Tilføj boundary i `validation_boundaries.py`:
```python
@dataclass
class UserBoundaries:
    # ...existing...
    phone_pattern: str = r"^\+\d{1,3}\d{3,14}$"
```

**Step 2:** Tilføj field i schema:
```python
class UserCreate(UserBase):
    phone_number: Optional[str] = Field(
        default=None,
        description="International phone number format"
    )
    
    @field_validator('phone_number')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(USER_BVA.phone_pattern, v):
            raise ValueError("Invalid phone format")
        return v
```

**Step 3:** Skriv test:
```python
def test_user_phone_validation():
    valid = UserCreate(..., phone_number="+4540123456")
    
    with pytest.raises(ValidationError):
        UserCreate(..., phone_number="invalid")
```

---

## 7️⃣ Quick Reference - All BVA Boundaries

| Model | Field | Min | Max | Valid Values |
|-------|-------|-----|-----|------|
| Category | name | 1 | 30 | any text |
| Category | type | - | - | "income", "expense" |
| Budget | amount | 0.00 | - | any >= 0 |
| Budget | period | - | - | "weekly", "monthly", "yearly" |
| Goal | target_amount | 0.00 | - | any >= 0 |
| Goal | current_amount | 0.00 | target | any >= 0 |
| Account | name | 1 | 30 | any text |
| Transaction | amount | != 0 | - | any != 0 |
| User | username | 3 | 20 | \w+ (alphanumeric+_) |
| User | password | 8 | - | any >= 8 chars |
| PlannedTx | amount | != 0 | - | any != 0 |
| PlannedTx | date | - | today | future or current |
| AccountGroup | name | 1 | 30 | any text |
| AccountGroup | max_users | 1 | 20 | 1-20 |

---

## 8️⃣ Debugging Tips

### **Problem: Validation fails unexpectedly**

```bash
# 1. Check validation_boundaries.py
# 2. Check schema @field_validators
# 3. Run test to see exact error
pytest backend/tests/test_bva_*.py -v --tb=short

# 4. See detailed validation error
python3
>>> from backend.schemas.category import CategoryCreate
>>> CategoryCreate(name="", type="income")
# Shows ValidationError with details
```

### **Problem: Test doesn't match actual validation**

```bash
# Ensure you're using latest schema
>>> from importlib import reload
>>> import backend.schemas.category
>>> reload(backend.schemas.category)
```

### **Problem: Can't find where validation happens**

```bash
# Search for field name
grep -r "min_length" backend/schemas/
# Or check validation_boundaries.py
```

---

## ✨ Best Practices

✅ **DO:**
- ✅ Keep boundaries in `validation_boundaries.py`
- ✅ Use `@field_validator` for complex logic
- ✅ Test all boundary values
- ✅ Update tests when you change boundaries
- ✅ Use descriptive error messages

❌ **DON'T:**
- ❌ Put validation in services
- ❌ Hardcode constraints in multiple files
- ❌ Skip edge case testing
- ❌ Use vague error messages
- ❌ Validate in database only

---

## 📚 Files You Should Know

| File | Purpose | Edit? |
|------|---------|-------|
| `validation_boundaries.py` | Define all constraints | ✅ When changing bounds |
| `schemas/*.py` | Validate input with Pydantic | ✅ When adding validators |
| `test_bva_*.py` | Test all boundary values | ✅ When adding new bounds |
| `models/*.py` | Database models | ❌ Usually not for BVA |
| `services/*.py` | Business logic | ❌ Services trust schemas |

---

## 🎯 Your Next Steps

1. **Read** `BVA_IMPLEMENTATION_GUIDE.md` for deep dive
2. **Run tests**: `pytest backend/tests/test_bva_*.py -v`
3. **Try adding** a new validator (see Task examples above)
4. **Deploy** with confidence! Your validation is rock solid 🚀

---

## 💬 Need Help?

- **How do I change a boundary?** → See "Task: Change a boundary value"
- **How do I add validation?** → See "Task: Add validation to new field"
- **How do I test?** → See "Test Your Validations"
- **Where is validation defined?** → It's in `validation_boundaries.py` + `schemas/`

---

**You're all set! Your validation is now professional-grade.** ✨

**Question mark?** Check the files or the BVA guide! 📖
