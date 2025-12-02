# 🚀 Login System - Quick Start (5 min setup)

## Trin 1: Backend Dependencies (1 min)

```bash
# Terminal
pip install passlib[bcrypt]
pip install python-jose[cryptography]
```

## Trin 2: Update CORS i main.py (1 min)

```python
# backend/main.py - ADD THIS AT TOP
from fastapi.middleware.cors import CORSMiddleware

# ... efter app = FastAPI() ...

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Trin 3: Copy Frontend Files (2 min)

```bash
# Copy disse filer til dit frontend project:
cp src/App_WITH_AUTH.js src/App.js

# Files er allerede lavet:
✅ src/pages/LoginPage.js
✅ src/pages/RegisterPage.js
✅ src/context/AuthContext.js
✅ src/components/PrivateRoute.js
✅ src/components/Navigation.js
✅ src/styles/*.css
```

## Trin 4: Run Services (1 min)

**Terminal 1 - Backend:**
```bash
cd backend
uvicorn main:app --reload
# Runs on http://localhost:8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend/finans-tracker-frontend
npm start
# Opens http://localhost:3000
```

## ✅ You're Done!

Test det:
1. Browser: http://localhost:3000
2. Du bliver redirectet til `/login`
3. Klik "Opret konto her"
4. Registrer: username, email, password
5. Log ind
6. Se dashboard!

---

## 🎯 Hvad kan du nu?

✅ **Register** - Opret nye bruger-konti  
✅ **Login** - Log ind med brugernavn/email  
✅ **Protected Pages** - Dashboard/Transactions/osv  
✅ **Logout** - Log ud og tilbage til login  
✅ **Persistent Session** - Token gemmes i localStorage  
✅ **Auto-redirect** - Redirect baseret på auth status  

---

## 🔗 File Mapping

| Fil | Hvad | Status |
|-----|------|--------|
| `backend/auth.py` | JWT + password hashing | ✅ Ready |
| `backend/services/user_service.py` | Login logik | ✅ Updated |
| `backend/routers/users.py` | Login endpoint | ✅ Updated |
| `backend/models/user.py` | User model | ✅ Updated |
| `src/pages/LoginPage.js` | Login UI | ✅ Ready |
| `src/pages/RegisterPage.js` | Register UI | ✅ Ready |
| `src/context/AuthContext.js` | Auth state | ✅ Ready |
| `src/components/PrivateRoute.js` | Route protection | ✅ Ready |
| `src/components/Navigation.js` | Nav bar | ✅ Ready |
| `src/App.js` | MUST UPDATE | ⚠️ See Trin 3 |

---

## 🐛 If Something Breaks

**Backend won't start?**
```bash
# Check dependencies
pip list | grep -E "passlib|python-jose"

# Re-install
pip install --upgrade passlib[bcrypt] python-jose[cryptography]
```

**Frontend shows blank page?**
```bash
# Clear cache
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
npm start
```

**Login says "user not found"?**
1. Make sure you registered first
2. Check database has User table
3. Check user in database: `SELECT * FROM User;`

**CORS error?**
1. Check backend is running on port 8000
2. Check CORS middleware is in main.py
3. Check frontend calling `http://localhost:8000` (not `http://127.0.0.1`)

---

## 📖 Want More Details?

Read: `LOGIN_SYSTEM_IMPLEMENTATION.md` for:
- ✅ Complete technical details
- ✅ Security considerations
- ✅ Troubleshooting guide
- ✅ Next steps & features

---

**That's it! Login system is ready! 🎉**
