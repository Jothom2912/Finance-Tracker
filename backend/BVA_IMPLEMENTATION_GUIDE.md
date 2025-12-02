# 📘 Boundary Value Analysis (BVA) Implementation Guide

## 🎯 Oversigt

Din Finance Tracker app har brug for **validering på tre niveauer**:
1. **Models (SQLAlchemy)** - Database constraints
2. **Schemas (Pydantic)** ⭐ **PRIMÆR** - Input validering med BVA
3. **Services** - Kontekst-afhængig logik

---

## 🏗️ Arkitektur-anbefaling

### **1️⃣ Models - Kun basis constraints**

**Models skal IKKE indeholde BVA-logik!** De skal kun sikre databaseintegritet:

```python
# ✅ GODT - Models
class Category(Base):
    __tablename__ = "Category"
    
    idCategory = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(45), nullable=False)  # ← Database constraint
    type = Column(String(45), nullable=False)  # ← Database constraint
```

---

### **2️⃣ Schemas - 🌟 HVOR BVA TILHØRER**

**Schemas er det rigtige sted for BVA-validering** fordi:
- ✅ Validerer data FØR det når databasen
- ✅ Giver brugeren feedback på input
- ✅ Centraliseret validering på ét sted
- ✅ Pydantic har built-in validators

#### **Eksempel: Category Schema med BVA**

```python
from pydantic import BaseModel, Field, field_validator
from ..validation_boundaries import CATEGORY_BVA

class CategoryBase(BaseModel):
    name: str = Field(
        ...,
        min_length=CATEGORY_BVA.name_min_length,      # 1 char
        max_length=CATEGORY_BVA.name_max_length,      # 30 chars
        description="Category name (1-30 characters)"
    )
    type: str = Field(
        ...,
        description="Category type: 'income' or 'expense'"
    )

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """BVA: Type må være enten 'income' eller 'expense'"""
        if v not in CATEGORY_BVA.valid_types:
            raise ValueError(f"Type må være en af {CATEGORY_BVA.valid_types}, fik: {v}")
        return v

    @field_validator('name')
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """BVA: Navn må ikke være tomt eller kun mellemrum"""
        if not v or v.strip() == "":
            raise ValueError("Navn må ikke være tomt")
        return v.strip()
```

---

### **3️⃣ Services - Business Logic**

**Services håndterer KONTEKST-afhængig validering** - altså ting der kræver databasekald:

```python
def create_goal(db: Session, goal: GoalCreate) -> GoalModel:
    """Opretter mål - validering af kontekst"""
    
    # ✅ SERVICE-LEVEL: Kontekst-validering
    account = db.query(AccountModel).filter(
        AccountModel.idAccount == goal.Account_idAccount
    ).first()
    if not account:
        raise ValueError("Konto med dette ID findes ikke.")
    
    # ❌ IKKE HER: Input-validering (det gør Pydantic!)
    # if goal.target_amount < 0: ...  ← Pydantic gør dette!
    
    db_goal = GoalModel(**goal.model_dump())
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal
```

---

## 🔍 BVA-test eksempler for din data

Jeg har lavet `validation_boundaries.py` og `test_bva_validation.py` som eksempler.

### **Hvad testes:**

#### **Category (4.1)**
| Felt | Grænseværdier | Gyldig/Ugyldig |
|------|---|---|
| name | 0, 1, 30, 31 chars | ❌ ✅ ✅ ❌ |
| type | "income", "expense", "saving" | ✅ ✅ ❌ |
| description | 0, 200, 201 chars | ✅ ✅ ❌ |

#### **Budget (4.2)**
| Felt | Grænseværdier | Test |
|------|---|---|
| amount | -0.01, 0, 0.01 | ❌ ✅ ✅ |
| period | "weekly", "monthly", "yearly", "quarterly" | ✅ ✅ ✅ ❌ |
| dates | end ≤ start, end = start+1 dag | ❌ ✅ |

#### **Goal (4.3)**
| Felt | Grænseværdier | Test |
|------|---|---|
| target_amount | -0.01, 0, 0.01 | ❌ ✅ ✅ |
| current_amount | > target, = target, < target | ❌ ✅ ✅ |
| deadline | fortid, i dag, i morgen | ❌ ❌ ✅ |

---

## 📝 Implementeringschecklist

### **For hver model, udfyld:**

- [ ] **Identificer grænseværdier** fra din BVA-liste
- [ ] **Opret `validation_boundaries.py`** med alle boundaries (✅ JEG HAR GJORT)
- [ ] **Opdater schemas** med `@field_validator` decorators
- [ ] **Skriv tests** i `test_bva_validation.py`
- [ ] **Models** - Tilføj kun `CHECK` constraints hvis nødvendigt
- [ ] **Services** - Tilføj kontekst-validering (FK exists osv)

### **Validering-flow:**

```
User Input (JSON)
        ↓
    Pydantic Schema ⭐ (BVA validation happens here!)
        ↓
    Service (Check FK, business rules)
        ↓
    SQLAlchemy Model (Save to DB)
        ↓
    Database (Final integrity check)
```

---

## 🛠️ Eksempel: Implementer User Schema

Her er hvordan du implementerer User med BVA:

```python
# backend/schemas/user.py
from pydantic import BaseModel, Field, field_validator
import re
from ..validation_boundaries import USER_BVA

class UserCreate(BaseModel):
    username: str = Field(
        ...,
        min_length=USER_BVA.username_min_length,   # 3
        max_length=USER_BVA.username_max_length,   # 20
        description="Username (3-20 characters)"
    )
    password: str = Field(
        ...,
        min_length=USER_BVA.password_min_length,   # 8
        description="Password (minimum 8 characters)"
    )
    email: str = Field(
        ...,
        description="Valid email address"
    )

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """BVA: Email skal være valid format"""
        pattern = USER_BVA.email_pattern
        if not re.match(pattern, v):
            raise ValueError(f"Invalid email format: {v}")
        return v

    @field_validator('username')
    @classmethod
    def validate_username_alphanum(cls, v: str) -> str:
        """BVA: Username må kun indeholde alphanumeriske tegn + underscore"""
        if not re.match(r"^[a-zA-Z0-9_]+$", v):
            raise ValueError("Username må kun indeholde bogstaver, tal og underscore")
        return v
```

---

## 🚀 Næste trin

1. **Gennemgå alle dine models** - hvad skal valideres?
2. **Opdater schemas** med Field constraints + validators
3. **Test hver schema** med boundary values
4. **Update services** med kontekst-validering
5. **Run tests**: `pytest backend/tests/test_bva_validation.py -v`

---

## 📚 Pydantic Validators - Quick Reference

### **Field-level validators (простых constraints):**
```python
name: str = Field(..., min_length=1, max_length=30)
amount: float = Field(..., ge=0)  # >= 0
```

### **Model-level validators (kompleks logik):**
```python
@field_validator('field_name')
@classmethod
def validate_field(cls, v: str) -> str:
    if condition:
        raise ValueError("Custom error message")
    return v

# For cross-field validation:
@field_validator('end_date')
@classmethod
def validate_dates(cls, v, info):
    if 'start_date' in info.data:
        start = info.data['start_date']
        if v <= start:
            raise ValueError("...")
    return v
```

---

## ✨ Fordele ved denne tilgang

| Aspekt | Før | Efter |
|--------|-----|-------|
| Validering sker | I services/routers | I schemas ✅ |
| Fejlbeskeder | Dårlige | Gode + konsistente |
| Testing | Svært | Nemt (test schemas!) |
| Performance | DB fejl | Input fejl før DB |
| Vedligeholdelse | Spredt omkring | Centraliseret |

---

## 🔗 Reference til din kode

- **Boundaries defineret i**: `backend/validation_boundaries.py` ✅
- **Category schema opdateret**: `backend/schemas/category.py` ✅
- **Budget schema opdateret**: `backend/schemas/budget.py` ✅
- **Goal schema opdateret**: `backend/schemas/goal.py` ✅
- **Test eksempler**: `backend/tests/test_bva_validation.py` ✅

---

## ❓ Spørgsmål til dig

1. **Skal du validere andre fields** som jeg ikke har dækket? (Account, User, PlannedTransaction osv)
2. **Har du dine eget password-regler** (specialtegn, caps osv)?
3. **Hvad med internationalisering** af fejlbeskeder?

Lad mig vide hvis du gerne vil jeg implementerer flere schemas! 🚀
