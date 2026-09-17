# Sustha Frontend

Sustha frontend is a React, JavaScript, Vite, and Tailwind application for a hospital-style clinical login screen.

## Run locally

```bash
cd sustha/frontend
npm install
npm run dev
```

## Auth contract

The login screen posts to `/api/auth/login` with a unique doctor identifier and password:

```json
{
  "doctor_id": "DOC-10042",
  "password": "********",
  "remember_me": true
}
```

On successful authentication, the frontend redirects to `/patients`. Authentication should be backed by HTTP-only cookies, password hashing, generic invalid-login errors, rate limiting, lockout handling, and server-side authorization.
