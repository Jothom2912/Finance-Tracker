# 🚀 BVA Quick Reference Card

## En-side oversigt af implementeringen

### **Fil-struktur du skal have:**

```
backend/
├── validation_boundaries.py          ← Definitioner af alle BVA grænser ✅
├── schemas/
│   ├── category.py                   ← Med @field_validator ✅
│   ├── budget.py                     ← Med kompleks date logik ✅
│   ├── goal.py                       ← Med targetAmount >= currentAmount ✅
│   ├── account.py                    ← Med navn-validering ✅
│   └── ... (user.py, transaction.py osv kommer senere)
├── models/
│   └── ... (Models kun med DB constraints, IKKE BVA)
├── services/
│   └── ... (Services kun med kontekst-validering, f.eks. FK exists)
└── tests/
    └── test_bva_validation.py        ← Test hver schema ✅
```

---

## **Validation Flow (Vigtigt!)**

```
┌─────────────────────┐
│   Frontend (JSON)   │
│   {"name":"Test"}   │
└──────────┬──────────┘
           │
           ↓
┌────────────────────────────────────────┐
│  ⭐ Pydantic Schema Layer (VIGTIG!)    │
│  - Min/max length                      │
│  - Valid enum values                   │
│  - Cross-field validation              │
│  - Custom @field_validator             │
│  → Returnerer ValidationError hvis dårlig
└──────────┬───────────────────────────────┘
           │ (Valid = fortsætter)
           ↓
┌────────────────────────────────────────┐
│     Service Layer                      │
│  - Check if FK exists (Account exists?)│
│  - Business rules                      │
│  → Returnerer ValueError hvis error    │
└──────────┬───────────────────────────────┘
           │ (Passes)
           ↓
┌────────────────────────────────────────┐
│    SQLAlchemy Model                    │
│  - Database integrity (NOT NULL osv)   │
│  - Constraints                         │
└──────────┬───────────────────────────────┘
           │
           ↓
┌────────────────────────────────────────┐
│      Database                          │
│  - Final safety check                  │
└────────────────────────────────────────┘
```

---

## **Tre mønstre du bruger:**

### **1. Field-level (Simpel)**
```python
name: str = Field(..., min_length=1, max_length=30)
amount: float = Field(..., ge=0)  # >= 0
period: str = Field(..., min_length=1)
```

### **2. Validator-level (Enum)**
```python
@field_validator('type')
@classmethod
def validate_type(cls, v: str) -> str:
    if v not in ["income", "expense"]:
        raise ValueError("...")
    return v
```

### **3. Cross-field validator (Kompleks)**
```python
@field_validator('current_amount')
@classmethod
def validate_vs_target(cls, v: float, info) -> float:
    if 'target_amount' in info.data:
        target = info.data['target_amount']
        if v > target:  # ← Brug info.data for at se andre fields!
            raise ValueError("current > target")
    return v
```

---

## **Boundary Values du skal teste - TL;DR**

| Entity | Field | Boundaries | Test Values |
|--------|-------|-----------|------------|
| **Category** | name | 1-30 chars | "", "A", "A"*30, "A"*31 |
| | type | income/expense | "income", "saving" ❌ |
| **Budget** | amount | >= 0 | -0.01, 0, 0.01 |
| | period | weekly/monthly/yearly | "daily" ❌ |
| | dates | end > start | end=start, end=start+1day ✅ |
| **Goal** | target_amount | >= 0 | -0.01, 0, 0.01 |
| | current <= target | logic | current=100/target=101 ❌ |
| | deadline | future only | yesterday ❌, tomorrow ✅ |
| **Account** | name | 1-30 chars | "", "A", "A"*30 |
| **User** | username | 3-20 chars | "ab" ❌, "abc" ✅, "a"*20 ✅ |
| | password | >= 8 chars | "Pass123" ❌, "Pass1234" ✅ |
| | email | valid format | "a@b.dk" ✅, "@b.dk" ❌ |

---

## **Hvad jeg har lavet til dig:**

✅ `validation_boundaries.py` - Alle grænseværdier defineret  
✅ `schemas/category.py` - Med navn/type validators  
✅ `schemas/budget.py` - Med amount, period, date validators  
✅ `schemas/goal.py` - Med kompleks logik (current vs target, deadline)  
✅ `schemas/account.py` - Med navn-validering  
✅ `tests/test_bva_validation.py` - Test eksempler for alle  
✅ `BVA_IMPLEMENTATION_GUIDE.md` - Fuld dokumentation  

---

## **Hvad du skal lave:**

- [ ] Opdater `schemas/transaction.py` med amount != 0 validering
- [ ] Opdater `schemas/planned_transaction.py` med amount != 0 og interval validering
- [ ] Opdater `schemas/user.py` med username/password/email validering
- [ ] Opdater `schemas/account_groups.py` med name og max_users validering
- [ ] Kør tests: `pytest backend/tests/test_bva_validation.py -v`
- [ ] Update services med FK kontekst-validering

---

## **Testing eksempel:**

```bash
# Kør alle BVA tests
pytest backend/tests/test_bva_validation.py -v

# Kør kun Category tests
pytest backend/tests/test_bva_validation.py::test_category_name_boundary_values -v

# Kør med coverage
pytest backend/tests/test_bva_validation.py --cov=backend.schemas --cov-report=html
```

---

## **Common mistakes at undgå:**

❌ Putting BVA logic in models  
❌ Putting BVA logic in services  
❌ Using `== 0.0` for floating point (brug tolerance)  
❌ Forgetting to validate in routers  
❌ Not testing boundary values  

✅ Put BVA in schemas!  
✅ Use Pydantic Field + @field_validator  
✅ Test boundaries: {min-1, min, max, max+1}  
✅ Services handle FK + business logic  

---

## **Hvis du skal udvide:**

Tilføj ny grænseværdi → `validation_boundaries.py`:
```python
@dataclass
class YourModelBoundaries:
    field_min: int = 1
    field_max: int = 30
```

Import i schema:
```python
from ..validation_boundaries import YOUR_MODEL_BVA

class YourSchema(BaseModel):
    field: str = Field(..., min_length=YOUR_MODEL_BVA.field_min)
```

Test:
```python
def test_your_field_boundaries():
    # -0.01 (invalid)
    # 0 (valid)
    # +0.01 (valid)
```

---

## **Next Steps:**

1. **Gennemgå** `validation_boundaries.py` - alle grænser der?
2. **Opdater** de sidste schemas (transaction, user, osv)
3. **Test** hver schema med boundary values
4. **Update** routers til at håndtere ValidationError
5. **Deploy** med tillid! 🚀

Spørg hvis du har brug for hjælp med en specifik schema! 💪
