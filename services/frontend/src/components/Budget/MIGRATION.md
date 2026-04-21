# Budget Component Refactoring - Migration Checklist

## Phase 1: Setup ✅ (Complete)

- [x] Create folder structure
- [x] Create domain layer (Budget entity, exceptions)
- [x] Create ports/interfaces
- [x] Create BudgetService
- [x] Create RestApiBudgetRepository adapter
- [x] Create useBudgetService hook
- [x] Create refactored BudgetSetup component
- [x] Create ARCHITECTURE.md documentation

## Phase 2: Component Migration (Next Steps)

### Step 1: Backup Original Components
```bash
# Backup the old components
mv Budget/BudgetSetup/BudgetSetup.jsx Budget/BudgetSetup/BudgetSetup.jsx.bak
mv Budget/BudgetComparison/BudgetComparison.jsx Budget/BudgetComparison/BudgetComparison.jsx.bak
mv Budget/BudgetItem/BudgetItem.jsx Budget/BudgetItem/BudgetItem.jsx.bak
```

### Step 2: Deploy Refactored Components

1. **Rename the refactored file:**
   ```bash
   mv Budget/BudgetSetup/BudgetSetup.refactored.jsx Budget/BudgetSetup/BudgetSetup.jsx
   ```

2. **Review changes in:** `services/frontend/src/components/Budget/BudgetSetup/BudgetSetup.jsx.bak`
   - Ensure all functionality is preserved
   - Compare diff between old and new

3. **Test the component:**
   - Create a budget
   - Update a budget
   - Delete a budget
   - Verify error handling
   - Verify success messages

### Step 3: Refactor BudgetComparison

Use the same pattern as BudgetSetup:
1. Move API logic to `RestApiBudgetRepository`
2. Use `useBudgetService` hook for state
3. Keep only presentation logic in component

```javascript
// OLD:
const response = await apiClient.get(`/budgets/?year=${year}`);

// NEW:
const { budgets, fetchBudgetsByYear } = useBudgetService();
await fetchBudgetsByYear(year);
```

### Step 4: BudgetItem Component

This is a **presentational component** - no changes needed!
- Takes `budget` and `categoryName` as props
- Handles only display logic
- Already following best practices

### Step 5: Update Any Imports

If other components import from Budget:

```javascript
// OLD:
import BudgetSetup from './Budget/BudgetSetup';

// NEW (same import, still works):
import BudgetSetup from './Budget/BudgetSetup';
```

### Step 6: Add Tests

Create test files:
```
Budget/
├── domain/
│   ├── Budget.js
│   ├── Budget.test.js         # ← NEW
│   └── exceptions.js
├── application/
│   ├── BudgetService.js
│   ├── BudgetService.test.js  # ← NEW
│   └── ports/
```

**Domain Test Example:**
```javascript
// domain/Budget.test.js
describe('Budget Entity', () => {
  test('validates positive amount', () => {
    const budget = new Budget({ amount: -10 });
    const { isValid } = budget.validate();
    expect(isValid).toBe(false);
  });

  test('detects duplicates', () => {
    const budget1 = new Budget({ category_id: 1, month: '01', year: '2024' });
    const budget2 = new Budget({ category_id: 1, month: '01', year: '2024' });
    expect(budget1.isDuplicate(budget2)).toBe(true);
  });
});
```

**Application Test Example:**
```javascript
// application/BudgetService.test.js
describe('BudgetService', () => {
  test('creates budget with valid data', async () => {
    const mockRepository = {
      save: jest.fn().mockResolvedValue(budget),
      findByYear: jest.fn().mockResolvedValue([])
    };
    
    const service = new BudgetService(mockRepository);
    const result = await service.createBudget(budget);
    
    expect(mockRepository.save).toHaveBeenCalled();
    expect(result.id).toBeDefined();
  });

  test('throws on duplicate budget', async () => {
    const mockRepository = {
      findByYear: jest.fn().mockResolvedValue([existingBudget])
    };
    
    const service = new BudgetService(mockRepository);
    
    await expect(service.createBudget(newBudget))
      .rejects.toThrow(BudgetDuplicateException);
  });
});
```

## Phase 3: Quality Assurance

- [ ] All tests passing
- [ ] No console errors
- [ ] Performance is same or better
- [ ] Error messages are user-friendly
- [ ] API calls still work correctly
- [ ] Form validation works
- [ ] Modal open/close works
- [ ] Budget comparison displays correctly

## Phase 4: Cleanup

- [ ] Delete old backup files (`.bak`)
- [ ] Update any related documentation
- [ ] Update CI/CD if needed
- [ ] Commit with message:
  ```
  refactor(budget): migrate to hexagonal architecture
  
  - Separate domain, application, and adapter layers
  - Extract business logic to BudgetService
  - Create RestApiBudgetRepository for API communication
  - Refactor BudgetSetup to use useBudgetService hook
  - Improve testability and maintainability
  ```

## Files Created

### Domain Layer
- ✅ `domain/Budget.js` - Budget entity
- ✅ `domain/exceptions.js` - Domain exceptions

### Application Layer
- ✅ `application/BudgetService.js` - Main service
- ✅ `application/ports/IBudgetService.js` - Inbound port
- ✅ `application/ports/IBudgetRepository.js` - Outbound port
- ✅ `application/index.js` - Exports

### Adapter Layer
- ✅ `adapters/inbound/useBudgetService.js` - React hook
- ✅ `adapters/outbound/RestApiBudgetRepository.js` - API adapter

### UI Components (To be migrated)
- ✅ `BudgetSetup/BudgetSetup.refactored.jsx` - Refactored component
- ⏳ `BudgetComparison/BudgetComparison.jsx` - Needs refactoring
- ✅ `BudgetItem/BudgetItem.jsx` - No changes needed

### Documentation
- ✅ `ARCHITECTURE.md` - Architecture guide
- ✅ `MIGRATION.md` - This file

## Rollback Plan

If something goes wrong:

```bash
# Restore from backup
mv Budget/BudgetSetup/BudgetSetup.jsx.bak Budget/BudgetSetup/BudgetSetup.jsx

# Or use git
git checkout HEAD -- services/frontend/src/components/Budget/
```

## Questions?

Refer to `ARCHITECTURE.md` for:
- Architecture overview
- Folder structure explanation
- Data flow diagrams
- Testing strategies
- How to add new features
