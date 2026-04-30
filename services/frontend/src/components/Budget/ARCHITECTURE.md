# Budget Component - Hexagonal Architecture

## Oversigt

Budget komponenten er refaktoreret fra en monolith til **hexagonal arkitektur** (ports and adapters). Dette giver os:

- ✅ **Separation of concerns** - UI, forretningslogik og data persistence er adskilt
- ✅ **Testability** - Kan mocke repositories for unit tests
- ✅ **Maintainability** - Ændringer i API påvirker ikke forretningslogik
- ✅ **Reusability** - Services kan bruges af andre komponenter

---

## Folder Structure

```
Budget/
├── domain/                           # ⭐ Forretningslogik
│   ├── Budget.js                    # Budget entity med validation
│   └── exceptions.js                # Domain exceptions
│
├── application/                      # 🎯 Use cases
│   ├── BudgetService.js             # Implementerer IBudgetService
│   ├── ports/
│   │   ├── IBudgetService.js        # Inbound port (what app can do)
│   │   └── IBudgetRepository.js     # Outbound port (how to persist)
│   └── index.js
│
├── adapters/
│   ├── inbound/                      # 📥 Input adapters (React hooks)
│   │   └── useBudgetService.js      # React hook med state management
│   │
│   └── outbound/                     # 📤 Output adapters (API client)
│       └── RestApiBudgetRepository.js # REST API implementation
│
├── ui/                               # 🎨 Presentational components
│   ├── BudgetSetup.jsx              # Form og list (refactored)
│   ├── BudgetComparison.jsx         # Comparison view
│   └── BudgetItem.jsx               # List item
│
├── BudgetSetup.css
├── BudgetComparison.css
└── BudgetItem.css
```

---

## Lag-Beskrivelser

### **Domain Layer** (forretningslogik)

**Ansvar:**
- Definere Budget entiteter
- Validerings regler
- Business logic

**Fil:** `domain/Budget.js`
```javascript
const budget = new Budget({
  category_id: 1,
  amount: 1000,
  month: '01',
  year: '2024'
});

// Validerer budget
const { isValid, errors } = budget.validate();

// Tjek dubletter
const isDuplicate = budget.isDuplicate(otherBudget);
```

---

### **Application Layer** (use cases)

**Ansvar:**
- Koordinerer domain og adapters
- Implementerer use cases
- Håndterer fejl

**Filer:**
- `application/BudgetService.js` - Implementering af IBudgetService
- `application/ports/IBudgetService.js` - Interface for use cases
- `application/ports/IBudgetRepository.js` - Interface for persistence

**Eksempel:**
```javascript
const service = new BudgetService(repository);

// Service validerer, tjekker dubletter, persisterer
await service.createBudget(budget);
```

---

### **Adapter Layer**

#### **Inbound Adapters** (React hooks)

**Ansvar:**
- Forbinde React komponenter til services
- State management
- Error handling

**Fil:** `adapters/inbound/useBudgetService.js`
```javascript
const {
  budgets,
  loading,
  error,
  createBudget,
  updateBudget,
  deleteBudget,
  fetchBudgetsByYear
} = useBudgetService();
```

#### **Outbound Adapters** (API Client)

**Ansvar:**
- HTTP kommunikation
- Data transformation
- Error mapping

**Fil:** `adapters/outbound/RestApiBudgetRepository.js`
```javascript
const repository = new RestApiBudgetRepository();
const budget = await repository.findByYear(2024);
```

---

## Data Flow

### **Create Budget Flow**

```
Component 
  ↓
useBudgetService hook 
  ↓
BudgetService (application)
  ├─ budget.validate() [domain]
  ├─ check duplicates
  └─ repository.save() [adapter]
    ↓
  RestApiBudgetRepository
    ↓
  API /budgets POST
    ↓
  Backend
```

---

## Migrering fra Monolith

### **Før (Monolith)**
```javascript
// BudgetSetup.jsx
function BudgetSetup() {
  const handleSubmit = async () => {
    const response = await apiClient.post('/budgets/', data);
    // validering blandet med API call
  };
}
```

### **Efter (Hexagonal)**
```javascript
// BudgetSetup.jsx
function BudgetSetup() {
  const { createBudget } = useBudgetService();
  
  const handleSubmit = async () => {
    const budget = new Budget(data);
    await createBudget(budget);
    // Clean separation
  };
}
```

---

## Testing Strategy

Med denne arkitektur kan du nemt teste hver layer:

### **Domain Testing**
```javascript
test('Budget validates correctly', () => {
  const budget = new Budget({ amount: -10 });
  const { isValid, errors } = budget.validate();
  expect(isValid).toBe(false);
});
```

### **Application Testing** (med mock repository)
```javascript
test('createBudget checks for duplicates', async () => {
  const mockRepository = {
    save: jest.fn(),
    findByYear: jest.fn().mockResolvedValue([existingBudget])
  };
  
  const service = new BudgetService(mockRepository);
  await expect(service.createBudget(budget))
    .rejects.toThrow(BudgetDuplicateException);
});
```

### **Component Testing** (med mock hook)
```javascript
jest.mock('../adapters/inbound/useBudgetService', () => ({
  useBudgetService: () => ({
    createBudget: jest.fn().mockResolvedValue(budget),
    budgets: [budget],
    loading: false,
    error: null
  })
}));
```

---

## Næste Skridt

1. **Refactor BudgetComparison** - Samme pattern som BudgetSetup
2. **Refactor BudgetItem** - Presentational component (ingen ændringer nødvendige)
3. **Add Unit Tests** - For domain layer
4. **Add Integration Tests** - For application layer med mock repository

---

## Vigtige Koncepter

| Koncept | Forklaring |
|---------|-----------|
| **Port** | Interface (IBudgetService, IBudgetRepository) |
| **Adapter** | Implementering af port (BudgetService, RestApiBudgetRepository) |
| **Domain** | Business rules og entities (Budget entity) |
| **Application** | Use cases og orchestration (BudgetService) |
| **Inbound** | Input til systemet (React komponenter via hooks) |
| **Outbound** | Output fra systemet (API calls via repository) |

---

## Eksempel: Adding New Feature

Skal du tilføje "Budget Templates"? Så tilføjer du:

1. **Domain:** `domain/BudgetTemplate.js`
2. **Service:** `BudgetTemplateService` implements `IBudgetTemplateService`
3. **Port:** `IBudgetTemplateRepository` 
4. **Adapter:** `RestApiBudgetTemplateRepository`
5. **Hook:** `useBudgetTemplateService`
6. **Component:** Bruge hooken

Ingen ændringer i eksisterende komponenter!

---

## Resources

- [Hexagonal Architecture - Alistair Cockburn](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters Pattern](https://en.wikipedia.org/wiki/Hexagonal_architecture_(software))
