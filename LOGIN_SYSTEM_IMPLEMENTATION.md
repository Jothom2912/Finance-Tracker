# 🔐 Login System Implementation Guide

## Oversigt

Jeg har implementeret et komplet login system for din Finance Tracker app baseret på din eksisterende logik. Her's hvad der blev lavet:

---

## ✅ Hvad blev implementeret?

### **Backend (Python/FastAPI)**

#### 1. **`backend/auth.py`** - Authentication logik
- ✅ Password hashing med bcrypt
- ✅ JWT token generation og validering
- ✅ Token ekspirering (60 minutter)
- ✅ Helper funktioner til token handling

**Vigtige funktioner:**
```python
hash_password(password)           # Hash password før gemning
verify_password(plain, hashed)   # Tjek password mod hash
create_access_token(...)          # Generér JWT token
decode_token(token)               # Dekoder JWT token
```

#### 2. **`backend/schemas/user.py`** - Updated
- ✅ Tilføjet `UserLogin` schema (username/email + password)
- ✅ Tilføjet `TokenResponse` schema
- ✅ BVA validering på username og password (fra tidligere)

#### 3. **`backend/services/user_service.py`** - Updated
- ✅ Tilføjet `login_user()` funktion
- ✅ Password hashing i `create_user()`
- ✅ Bruger-lookup by username eller email
- ✅ Password verification

#### 4. **`backend/routers/users.py`** - Updated
- ✅ Ny endpoint: `POST /users/login`
- ✅ Returnerer JWT token ved succesfuldt login
- ✅ Håndterer login fejl (401 Unauthorized)

#### 5. **`backend/models/user.py`** - Updated
- ✅ Bruger `password` felt (hashede password gemmes her)

---

### **Frontend (React)**

#### 1. **`src/pages/LoginPage.js`** - Login side
- ✅ Form med username/email + password
- ✅ Fejlhåndtering
- ✅ Loading state
- ✅ Link til registrering
- ✅ Gemmer token i localStorage ved succesfuldt login

#### 2. **`src/pages/RegisterPage.js`** - Registrering side
- ✅ Form med username + email + password
- ✅ Password bekræftelse
- ✅ Validation (password længde osv)
- ✅ Fejlhåndtering

#### 3. **`src/context/AuthContext.js`** - Auth state management
- ✅ Globalt auth context (bruger, token, loading)
- ✅ Login/logout funktioner
- ✅ Token gemmer i localStorage
- ✅ Automatisk restore session fra localStorage
- ✅ `useAuth()` hook til at bruge i komponenter

#### 4. **`src/components/PrivateRoute.js`** - Route protection
- ✅ Proteger routes som kræver login
- ✅ Redirect til login hvis IKKE authenticated
- ✅ Loading state mens auth check

#### 5. **`src/components/Navigation.js`** - Navigation bar
- ✅ Menu links (Dashboard, Transactions, Categories, Budget)
- ✅ Vis logged in bruger
- ✅ Logout button
- ✅ Sticky header

#### 6. **CSS Styling**
- ✅ `LoginPage.css` - Login page styling
- ✅ `RegisterPage.css` - Register page styling
- ✅ `Navigation.css` - Navigation bar styling
- ✅ Responsive design (mobile-friendly)

#### 7. **`src/App_WITH_AUTH.js`** - Updated App.js
- ✅ Router setup med auth routes
- ✅ AuthProvider wrapper
- ✅ PrivateRoute for protected pages
- ✅ Public routes (login, register)

---

## 🔄 Flow (User Experience)

```
1. Bruger åbner app
   ↓
2. Hvis IKKE logget ind → Login page
   Hvis logget ind → Dashboard
   ↓
3. Login page:
   - Indtast username/email + password
   - Klik "Log ind"
   ↓
4. Backend tjekker:
   - User eksisterer?
   - Password korrekt?
   ↓
5. Hvis OK:
   - Generér JWT token
   - Return token + user info
   ↓
6. Frontend:
   - Gem token i localStorage
   - Gem user info
   - Redirect til /dashboard
   ↓
7. Bruger kan nu:
   - Se dashboard (protected page)
   - Alle API calls bruger token som Authorization header
   - Se Navigation bar med brugernavn + logout
   ↓
8. Logout:
   - Klik "Log ud"
   - Fjern token fra localStorage
   - Redirect til /login
```

---

## 🛠️ Tekniske detaljer

### **Password Hashing (Backend)**

```python
# Når bruger oprettes
hashed_pwd = hash_password(user.password)  # bcrypt hash
# Gemmes i databasen

# Ved login
if verify_password(input_pwd, hashed_pwd):  # Sammenlign
    # Password correct!
```

### **JWT Token (Backend)**

```python
# Token indeholder:
{
  "user_id": 1,
  "username": "johan",
  "email": "johan@example.com",
  "exp": <timestamp 60 minutter fra nu>
}

# Signed med SECRET_KEY
# Frontend kan IKKE ændre token (ville blive ugyldigt)
```

### **Frontend Token Handling**

```javascript
// Login
const response = await fetch('/users/login', ...)
const data = response.json()

// Gem token
localStorage.setItem('access_token', data.access_token)

// Ved hver API call
const headers = {
  'Authorization': `Bearer ${token}`
}

// Logout
localStorage.removeItem('access_token')
```

---

## 📋 Dependencies

### **Backend kræver:**

```bash
# Pip install
pip install passlib[bcrypt]  # Password hashing
pip install python-jose[cryptography]  # JWT tokens
```

### **Frontend kræver:**

```bash
# Allerede installeret (React Router)
npm list react-router-dom
```

---

## 🚀 Setup Instructions

### **1. Backend Setup**

#### a) Install dependencies
```bash
cd backend
pip install passlib[bcrypt]
pip install python-jose[cryptography]
```

#### b) Update main.py
```python
# backend/main.py
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from .routers import users, transactions, categories, budgets, goals, accounts
app.include_router(users.router)
app.include_router(transactions.router)
# ... rest af routers
```

#### c) Run backend
```bash
cd backend
uvicorn main:app --reload
# Server runs på http://localhost:8000
```

### **2. Frontend Setup**

#### a) Update App.js
```bash
# Erstatt din gamle App.js med indholdet fra App_WITH_AUTH.js
cp src/App_WITH_AUTH.js src/App.js
```

#### b) Install dependencies (hvis needed)
```bash
npm install react-router-dom
# Allerede der - bare tjek at det virker
```

#### c) Run frontend
```bash
cd frontend/finans-tracker-frontend
npm start
# Opens på http://localhost:3000
```

### **3. Database Setup**

```bash
# Din database burde allerede have User tabel
# Men password field skal være STRING(255) eller længere
```

---

## ✨ Features

### **Sikkerhed**
- ✅ Password hashing med bcrypt
- ✅ JWT token med expiration
- ✅ Protected routes (private pages)
- ✅ Token validation på backend

### **User Experience**
- ✅ Smooth login/register flow
- ✅ Auto-redirect baseret på auth status
- ✅ Remember user (localStorage)
- ✅ Beautiful UI med gradient
- ✅ Error messages
- ✅ Loading states

### **Developer Experience**
- ✅ Easy to use `useAuth()` hook
- ✅ Easy to protect routes with `<PrivateRoute>`
- ✅ Centralized auth logic
- ✅ Clear separation of concerns

---

## 🔗 Data Flow (Eksempel: Login)

### **Frontend → Backend**

```javascript
// LoginPage.js
POST http://localhost:8000/users/login
{
  "username_or_email": "johan",
  "password": "mypassword123"
}
```

### **Backend Processing**

```python
# users.py router
@router.post("/login")
def login_route(credentials: UserLogin, db: Session):
    # Routen modtager credentials
    token = user_service.login_user(db, credentials.username_or_email, credentials.password)
    # user_service tjekker:
    # 1. User exists (by username eller email)
    # 2. Password matches (verify_password)
    # 3. Generér JWT token
    # 4. Return token
```

### **Response → Frontend**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user_id": 1,
  "username": "johan",
  "email": "johan@example.com"
}
```

### **Frontend Storage**

```javascript
// AuthContext.js
localStorage.setItem('access_token', data.access_token)
localStorage.setItem('user_id', data.user_id)
localStorage.setItem('username', data.username)

// AuthProvider updaterer state
setUser({ id: user_id, username: username })
setToken(access_token)
```

---

## 🐛 Troubleshooting

### **"Login fejler med 401"**

**Problem:** `ValueError: Brugernavn eller email ikke fundet`

**Løsning:**
1. Tjek at bruger eksisterer i databasen
2. Tjek at email er stavet korrekt
3. Tjek at password er korrekt

### **"Token invalid"**

**Problem:** `JWTError: Invalid token`

**Løsning:**
1. Tjek at `SECRET_KEY` i `auth.py` er korrekt
2. Tjek at token ikke er udløbet (60 minutter)
3. Tjek at `Authorization` header er korrekt format: `Bearer <token>`

### **"CORS error"**

**Problem:** `Access to XMLHttpRequest has been blocked by CORS policy`

**Løsning:**
1. Tjek at CORS middleware er setup i `main.py`
2. Tjek at `allow_origins` inkluderer frontend URL

### **"localStorage is undefined"**

**Problem:** Bruger får fejl i browser console

**Løsning:**
1. Dette sker kun i SSR (Server-Side Rendering)
2. Wrap localStorage code i `if (typeof window !== 'undefined')`

### **"Password hashing fejler"**

**Problem:** `ModuleNotFoundError: No module named 'passlib'`

**Løsning:**
```bash
pip install passlib[bcrypt]
```

---

## 📊 User Flow Diagram

```
App Start
    ↓
Check localStorage for token
    ├─ Token exists? → Set user + token
    └─ No token? → Set user = null
    ↓
Route protection
    ├─ Public route (/login, /register) → Allow
    ├─ Private route + authenticated → Allow
    └─ Private route + NOT authenticated → Redirect to /login
    ↓
Login Page (if not authenticated)
    ├─ Enter username/email + password
    ├─ POST /users/login
    ├─ Success → Save token + user info → Redirect to /dashboard
    └─ Error → Show error message
    ↓
Dashboard (if authenticated)
    ├─ Show Navigation bar
    ├─ User can browse protected pages
    ├─ All API calls use Authorization header
    └─ User can logout
    ↓
Logout
    ├─ Clear localStorage
    ├─ Clear auth context
    └─ Redirect to /login
```

---

## 📝 Integration Checklist

- [ ] Install backend dependencies (passlib, python-jose)
- [ ] Update `backend/main.py` med CORS middleware
- [ ] Test backend: `uvicorn main:app --reload`
- [ ] Replace `src/App.js` med `src/App_WITH_AUTH.js`
- [ ] Test frontend: `npm start`
- [ ] Test login flow (register → login → dashboard → logout)
- [ ] Verify JWT token is stored in localStorage
- [ ] Verify protected routes redirect to login
- [ ] Test with multiple users

---

## 🎓 Next Steps

1. **Customize LOGIN PAGE** - Tilføj dit branding
2. **Customize NAVIGATION** - Ændre farver, fonts osv
3. **ADD PASSWORD RESET** - "Forgot password?" feature
4. **ADD USER PROFILE** - Se/rediger user info
5. **ADD REFRESH TOKEN** - Longer session duration
6. **ADD 2FA** - Two-factor authentication
7. **ADD OAUTH** - Google/GitHub login
8. **ADD ROLE-BASED ACCESS** - Admin vs User permissions

---

## 💡 Pro Tips

### **For Development:**
- Sæt `ALGORITHM = "HS256"` (default)
- Sæt `ACCESS_TOKEN_EXPIRE_MINUTES = 60` (default)
- Brug `http://localhost:3000` for frontend CORS

### **For Production:**
- Skift `SECRET_KEY` til random string: `openssl rand -hex 32`
- Sæt `ACCESS_TOKEN_EXPIRE_MINUTES` til 30 eller 15
- Bruge HTTPS
- Bruge environment variables for SECRET_KEY
- Sæt `allow_origins` til dit rigtige domain

### **Security Best Practices:**
- Aldrig gemme plain text password
- Aldrig log sensitive data
- Altid valider input (Pydantic gør dette)
- Altid bruge HTTPS i production
- Rotér SECRET_KEY regelmæssigt
- Monitor for unauthorized access attempts

---

## 📚 References

- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Passlib Documentation](https://passlib.readthedocs.io/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8949)
- [React Router v6](https://reactrouter.com/)

---

**Du er nu klar til at bruge login systemet! 🚀**

Hvis du har spørgsmål, check troubleshooting eller kontakt mig!
