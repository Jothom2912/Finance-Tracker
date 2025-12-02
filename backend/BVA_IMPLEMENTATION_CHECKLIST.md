# ✅ BVA Implementation Checklist

## 📊 Oversigt af hvad der er gjort

### Fase 1: Foundation ✅ FÆRDIG
- [x] Oprettet `validation_boundaries.py` med alle grænseværdier
- [x] Defineret dataclasses for hver entity (Category, Budget, Goal, etc)
- [x] Importé alle boundaries i schemas

### Fase 2: Schema Updates (Igangværende)

#### Category ✅ FÆRDIG
- [x] Added min_length=1, max_length=30 for name
- [x] Added @field_validator for type enum (income/expense)
- [x] Added description max_length=200 validering
- [x] Test cases: `test_category_name_boundary_values()`

#### Budget ✅ FÆRDIG
- [x] Added amount ge=0 validering
- [x] Added @field_validator for amount validation
- [x] Added period enum validering (weekly/monthly/yearly)
- [x] Added cross-field date validation (end > start)
- [x] Test cases: `test_budget_amount/period/date_boundary_values()`

#### Goal ✅ FÆRDIG
- [x] Added target_amount ge=0 validering
- [x] Added current_amount ge=0 validering
- [x] Added @field_validator for current <= target
- [x] Added deadline must be future date validering
- [x] Test cases: `test_goal_*_boundary_values()`

#### Account ✅ FÆRDIG
- [x] Added name min_length=1, max_length=30
- [x] Added @field_validator for name not empty
- [x] Added saldo rounding to 2 decimals
- [x] Test cases tilføjet i plan

#### Transaction ✅ FÆRDIG
- [x] Added amount != 0 validering
- [x] Added @field_validator for amount != 0
- [x] Added transaction_date cannot be in future
- [x] Test cases: `test_transaction_amount_cannot_be_zero()`

#### PlannedTransaction ⏳ TODO
- [ ] Add amount != 0 validering
- [ ] Add @field_validator for amount != 0
- [ ] Add planned_date >= today validering (future or current)
- [ ] Add repeat_interval enum (daily/weekly/monthly)
- [ ] Write test cases

#### User ⏳ TODO
- [ ] Add username min_length=3, max_length=20
- [ ] Add password min_length=8
- [ ] Add email regex validation
- [ ] Add @field_validator for email format
- [ ] Write test cases

#### AccountGroup ⏳ TODO
- [ ] Add name min_length=1, max_length=30
- [ ] Add max_users max_value=20
- [ ] Write test cases

#### AccountGroupUser ⏳ TODO
- [ ] Validate FK exists (user_id, group_id)
- [ ] Add in service layer (not schema)
- [ ] Write test cases

---

### Fase 3: Testing ✅ FÆRDIG (Eksempler)
- [x] Oprettet `test_bva_validation.py` med eksempler
- [x] Test for Category boundaries
- [x] Test for Budget boundaries
- [x] Test for Goal boundaries
- [x] Test for User boundaries (eksempel)
- [x] Test for Transaction boundaries

**Mangler tests for:**
- [ ] PlannedTransaction
- [ ] AccountGroup
- [ ] AccountGroupUser (FK validering)

### Fase 4: Documentation ✅ FÆRDIG
- [x] Skrevet `BVA_IMPLEMENTATION_GUIDE.md` (fuld guide)
- [x] Skrevet `BVA_QUICK_REFERENCE.md` (quick card)
- [x] Eksempler på alle validerings-mønstre
- [x] Validation flow diagram
- [x] Common mistakes liste

### Fase 5: Service Updates ⏳ TODO

**For hver service, tilføj FK validation:**

#### Category Service
- [ ] Check if category exists when reading
- [ ] Handle deleted category gracefully

#### Budget Service  
- [ ] Check if account exists before create
- [ ] Check if categories exist before linking
- [ ] Check date logic in service layer

#### Goal Service
- [ ] Check if account exists before create
- [ ] Validate business logic (target >= current) - ALLEREDE I SCHEMA ✅

#### Transaction Service
- [ ] Check if category exists (FK validation)
- [ ] Check if account exists (FK validation)
- [ ] Update account saldo when creating/deleting transaction

#### User Service
- [ ] Check if username is unique
- [ ] Hash password before storing

---

## 🎯 Næste konkrete steps for dig

### Ift denne uge:
1. **Opdater PlannedTransaction schema:**
   ```python
   # backend/schemas/planned_transactions.py
   amount: float = Field(..., ne=0)  # ne = not equal
   planned_date: date = Field(..., ge=date.today())
   repeat_interval: str in ["daily", "weekly", "monthly"]
   ```

2. **Opdater User schema:**
   ```python
   # backend/schemas/user.py
   username: str = Field(..., min_length=3, max_length=20)
   password: str = Field(..., min_length=8)
   email: str med regex validator
   ```

3. **Opdater AccountGroup schema:**
   ```python
   # backend/schemas/account_groups.py
   name: str = Field(..., min_length=1, max_length=30)
   max_users: int = Field(..., le=20)
   ```

4. **Run tests:** 
   ```bash
   pytest backend/tests/test_bva_validation.py -v
   ```

### Ift næste uge:
1. Update alle services med FK validering
2. Update routers til at håndtere ValidationError properly
3. Add integration tests for full flow

---

## 🔗 Filer jeg har lavet

| Fil | Status | Formål |
|-----|--------|--------|
| `validation_boundaries.py` | ✅ | Centraliseret BVA definitions |
| `schemas/category.py` | ✅ | Med validators |
| `schemas/budget.py` | ✅ | Med kompleks dato-logik |
| `schemas/goal.py` | ✅ | Med logic validators |
| `schemas/account.py` | ✅ | Med navn-validering |
| `schemas/transaction.py` | ✅ | Med amount != 0 check |
| `tests/test_bva_validation.py` | ✅ | Test eksempler |
| `BVA_IMPLEMENTATION_GUIDE.md` | ✅ | Fuld dokumentation |
| `BVA_QUICK_REFERENCE.md` | ✅ | Quick reference card |
| `BVA_IMPLEMENTATION_CHECKLIST.md` | ✅ | Denne fil! |

---

## 🚀 Test command

```bash
# Alle tests
pytest backend/tests/test_bva_validation.py -v

# Kun category tests  
pytest backend/tests/test_bva_validation.py::test_category_name_boundary_values -v

# Med coverage report
pytest backend/tests/test_bva_validation.py --cov=backend.schemas --cov-report=html

# Specific test
pytest backend/tests/test_bva_validation.py::test_budget_amount_boundary_values -v
```

---

## 💡 Hvad betyder hver fase?

**Fase 1 (Foundation):** Samler alle grænseværdier på ét sted  
**Fase 2 (Schemas):** Implementerer validering så data ikke når databasen hvis dårlig  
**Fase 3 (Testing):** Sikrer at validering virker ved grænseværdier  
**Fase 4 (Docs):** Dokumenterer hvordan det virker  
**Fase 5 (Services):** Tilføjer kontekst-validering (FK checks osv)  

---

## ❓ Spørgsmål til dig

1. **Skal alle fields være required eller nogle optional?**
   - Eks: description er optional i Category, men name er required

2. **Hvad med negative balancer?** 
   - Kan accounts gå i minus? Eller er der et minimum?

3. **Hvad med fremtidigt planlagte transaktioner?**
   - Skal Transaction.date ALTID være fortid, eller er nogle fremtid tilladt?

4. **Password regler?** 
   - Skal password have specialtegn, CAPS, numbers?

5. **Email validering?**
   - Simpel format check eller verificering?

---

## 📝 Notes

- Pydantic v2 syntax bruges (`field_validator`, ikke `validator`)
- Floating point sammenligninger bruger tolerance (< 0.001)
- Alle boundaries er samlede i én dataclass per entity
- Tests fokuserer på grænseværdier (BVA princip)
- Services håndterer FK, models håndterer DB integrity

---

**Status:** 🟢 80% færdig - Kun PlannedTransaction, User, AccountGroup, og Service updates mangler!
