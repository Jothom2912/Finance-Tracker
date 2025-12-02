# 🏗️ BVA Architecture & Design Patterns

## Model-Schema-Service arkitektur

```
┌──────────────────────────────────────────────────────────────────┐
│                     CLIENT (Frontend)                            │
│                   Sender JSON data                               │
└────────────────────────────┬─────────────────────────────────────┘
                             │ POST /api/categories
                             │ {name: "Groceries", type: "expense"}
                             ↓
┌────────────────────────────────────────────────────────────────────┐
│                    🟢 ROUTER LAYER                                 │
│              (receives request, passes to service)                │
│                                                                    │
│  @app.post("/categories/")                                        │
│  async def create_category(category: CategoryCreate):             │
│      return category_service.create_category(db, category)       │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ↓
┌────────────────────────────────────────────────────────────────────┐
│              ⭐ SCHEMA LAYER (Pydantic)                           │
│          ← DATA VALIDATION HAPPENS HERE ←                        │
│                                                                    │
│  class CategoryCreate(BaseModel):                                 │
│      name: str = Field(min_length=1, max_length=30)              │
│      type: str                                                    │
│                                                                    │
│      @field_validator('type')                                    │
│      def validate_type(cls, v):                                  │
│          if v not in ["income", "expense"]:                      │
│              raise ValidationError(...)                          │
│          return v                                                │
│                                                                    │
│  ❌ ValidationError thrown if invalid → 422 response to client  │
│  ✅ Valid data continues                                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │ (Valid CategoryCreate instance)
                             ↓
┌────────────────────────────────────────────────────────────────────┐
│                  🟡 SERVICE LAYER                                 │
│        (Business logic, FK validation, etc)                       │
│                                                                    │
│  def create_category(db: Session, cat: CategoryCreate):          │
│                                                                    │
│      # Check if name already exists (business rule)              │
│      if db.query(Category).filter(...).first():                  │
│          raise ValueError("Category name exists")                │
│                                                                    │
│      db_cat = Category(**cat.model_dump())                       │
│      db.add(db_cat)                                              │
│      db.commit()                                                 │
│      return db_cat                                               │
│                                                                    │
│  ❌ ValueError thrown if business rule fails                     │
│  ✅ Continue to model/database                                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │ (CategoryModel instance)
                             ↓
┌────────────────────────────────────────────────────────────────────┐
│                🔵 MODEL LAYER (SQLAlchemy)                         │
│          (Database representation & integrity)                    │
│                                                                    │
│  class Category(Base):                                            │
│      __tablename__ = "Category"                                  │
│      idCategory = Column(Integer, PK)                            │
│      name = Column(String(45), nullable=False, unique=True)     │
│      type = Column(String(45), nullable=False)                  │
│                                                                    │
│  ← Only database constraints, NO validation logic                │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ↓
┌────────────────────────────────────────────────────────────────────┐
│                    💾 DATABASE                                     │
│                   (Final safety check)                            │
└────────────────────────────────────────────────────────────────────┘
```

---

## Error Handling Flow

```
        Input Data
             │
             ↓
    ┌────────────────────┐
    │  Pydantic Schema   │  ← ValidationError (400/422 response)
    │  Validators        │     Brugeren får: "name must be 1-30 chars"
    └─────────┬──────────┘
              │ Valid
              ↓
    ┌────────────────────┐
    │  Service Layer     │  ← ValueError/Exception (500 response)
    │  Business Rules    │     Brugeren får: "Category name already exists"
    └─────────┬──────────┘
              │ OK
              ↓
    ┌────────────────────┐
    │  SQLAlchemy Model  │  ← IntegrityError (500 response)
    │  DB Constraints    │     Brugeren får: "Database integrity error"
    └─────────┬──────────┘
              │ Success
              ↓
         Response 201
       (Resource created)
```

---

## Validation Patterns - Sammenfatning

### Pattern 1: Simple Field Constraints
```python
# For: length constraints, numeric ranges, patterns
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=20)
    age: int = Field(..., ge=0, le=150)
```
✅ Bruges når grænsen er simpel og uafhængig af andre fields

### Pattern 2: Enum Validation
```python
# For: restricted set of values
@field_validator('type')
@classmethod
def validate_type(cls, v: str) -> str:
    valid_types = ["income", "expense"]
    if v not in valid_types:
        raise ValueError(f"type must be one of {valid_types}")
    return v
```
✅ Bruges når der kun er nogle få gyldige værdier

### Pattern 3: Cross-Field Validation
```python
# For: validering der afhænger af andre fields
@field_validator('current_amount')
@classmethod
def validate_vs_target(cls, v: float, info) -> float:
    if 'target_amount' in info.data:
        target = info.data['target_amount']
        if v > target:
            raise ValueError("current cannot exceed target")
    return v
```
✅ Bruges når to eller flere fields skal valideres sammen

### Pattern 4: Custom Validation Logic
```python
# For: kompleks business logik
@field_validator('email')
@classmethod
def validate_email(cls, v: str) -> str:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, v):
        raise ValueError("Invalid email format")
    return v
```
✅ Bruges når der skal regex eller kompleks logik til

---

## Grænseværdi-tænkning (BVA Mindset)

For hvert felt skal du spørge:

### ✅ Hvad er det MINDSTE input jeg accepterer?
```
Eksempel - name: min_length=1
- Input: "" (empty) → INVALID
- Input: "A" (1 char) → VALID ✅

Eksempel - amount: ge=0
- Input: -0.01 → INVALID
- Input: 0 → VALID ✅
```

### ✅ Hvad er det STØRSTE input jeg accepterer?
```
Eksempel - name: max_length=30
- Input: "A" * 30 (30 chars) → VALID ✅
- Input: "A" * 31 (31 chars) → INVALID

Eksempel - username: max_length=20
- Input: "a" * 20 → VALID ✅
- Input: "a" * 21 → INVALID
```

### ✅ Hvad er "lige uden for grænsen"?
```
Eksempel - boundary testing
- Test: min-1, min, max, max+1
- For name length: "", "A", "A"*30, "A"*31
- For amount: -0.01, 0, 0.01
```

### ✅ Hvad er ugyldige værdier?
```
Eksempel - enums
- type valid: ["income", "expense"]
- type invalid: "saving", "transfer", "", None
```

### ✅ Hvad afhænger af andre felter?
```
Eksempel - cross-field
- goal: current_amount <= target_amount
- budget: end_date > start_date
- transaction: amount != 0
```

---

## Praktisk checklist ved nyt felt

Når du tilføjer et nyt felt, spørg disse:

```
1. ☐ Hvilken TYPE er det? (str, int, float, date, enum)
2. ☐ Er det REQUIRED eller OPTIONAL?
3. ☐ Hvad er MINIMUM værdi/længde?
4. ☐ Hvad er MAKSIMUM værdi/længde?
5. ☐ Er der specielle REGLER? (f.eks. != 0, future date)
6. ☐ Afhænger det af ANDRE FELTER?
7. ☐ Hvad er UGYLDIGE VÆRDIER?
8. ☐ Hvordan skal ERROR-BESKED være?

Eksempel for "goal deadline":
1. TYPE: date
2. REQUIRED: Ja (hvis databasen siger så)
3. MIN: date.today() + 1 dag
4. MAX: Ingen øvre grænse (unlimited future)
5. REGLER: Skal være i fremtiden
6. AFHÆNGER: Nej (uafhængigt felt)
7. UGYLDIGT: Fortiden, i dag
8. ERROR: "Deadline must be in the future"
```

---

## Service-lag FK validering eksempel

```python
# backend/services/goal_service.py

def create_goal(db: Session, goal: GoalCreate) -> GoalModel:
    """
    Service layer håndterer:
    1. FK validation (Account exists?)
    2. Business rules (kontekst-afhængig)
    3. Data manipulation
    
    Input validation er ALLEREDE done af Pydantic schema!
    """
    
    # ✅ SERVICE: Check if referenced account exists
    account = db.query(AccountModel).filter(
        AccountModel.idAccount == goal.Account_idAccount
    ).first()
    
    if not account:
        raise ValueError(
            f"Account with ID {goal.Account_idAccount} not found"
        )
    
    # ❌ DON'T do validation here - Pydantic already did it:
    # if goal.target_amount < 0: ...  ← Schema validates this!
    # if goal.current_amount > goal.target_amount: ...  ← Schema validates!
    
    # ✅ Continue with business logic
    db_goal = GoalModel(**goal.model_dump())
    db.add(db_goal)
    db.commit()
    db.refresh(db_goal)
    return db_goal
```

---

## Database Level - Hvornår bruges CHECK constraints?

```sql
-- Database kan også have constraints (ekstra sikkerhed)

CREATE TABLE Goal (
    idGoal INT PRIMARY KEY,
    target_amount DECIMAL(15, 2),
    current_amount DECIMAL(15, 2),
    Account_idAccount INT,
    
    -- Schema-lag tjekker dette, men database tjekker også:
    CHECK (target_amount >= 0),
    CHECK (current_amount >= 0),
    CHECK (current_amount <= target_amount),  -- Cross-field!
    
    FOREIGN KEY (Account_idAccount) REFERENCES Account(idAccount)
);
```

✅ **Hvor bruge hvad:**
- **Pydantic Schema**: Input validation (FØR database)
- **Service Layer**: Business rules & FK checks
- **SQLAlchemy Model**: Relationer & cascade rules
- **Database**: Sidste forsvar (constraints, FK integrity)

---

## Summary: Tre niveauer af sikkerhed

| Niveau | Hvad | Hvis fejl |
|--------|------|----------|
| 🟢 **Schema** | Type, length, enum, cross-field logic | ValidationError → 422 response |
| 🟡 **Service** | FK exists, business rules, duplicates | ValueError → 500 response |
| 🔵 **Database** | NOT NULL, UNIQUE, FK constraints, CHECK | IntegrityError → 500 response |

Brugeren ser fejl på niveau 🟢 først (best case, fejl i input)
Hvis fejl slipper gennem, fanges de på 🟡 eller 🔵 (worst case)

---

**Denne arkitektur sikrer at:**
- ✅ Dårlig data aldrig når databasen
- ✅ Brugeren får klar feedback
- ✅ Systemet er robust
- ✅ Koden er vedligeholdelig
