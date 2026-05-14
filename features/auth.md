# auth.md — Authentication & Account Management

## What this covers

Signup, login (email + Google), email verification, JWT issuance, token refresh, logout, account deletion.

## Flows

### Email signup
1. User submits `{ email, password, name }` to `POST /auth/signup`
2. Backend:
   - Validates: email format, password ≥ 8 chars, name not empty
   - Checks email not in use → 409 if taken
   - Hashes password with **argon2** (not bcrypt — argon2 is the modern default)
   - Creates `users` row with `email_verified=false`
   - Creates `email_verifications` row with 6-digit code, 15 min expiry
   - Sends verification email (FastAPI BackgroundTasks for v1)
   - Issues JWT pair and returns
3. User can use the app immediately but is gently prompted to verify email
4. User submits code to `POST /auth/verify-email` → sets `email_verified=true`

### Email login
1. `POST /auth/login` with `{ email, password }`
2. Look up user, verify argon2 hash
3. 401 if wrong (generic "invalid email or password" — don't leak which)
4. Issue JWT pair

### Google login
1. Mobile app uses Expo's `expo-auth-session` to get Google `id_token`
2. App sends `id_token` to `POST /auth/google`
3. Backend verifies token with Google's tokeninfo endpoint
4. If `google_id` exists in `users` → log them in
5. If email exists but no `google_id` → link the Google account to existing user
6. If neither → create new user with `email_verified=true` (Google already verified it)

### Token refresh
1. Mobile detects 401 on any request
2. Calls `POST /auth/refresh` with `{ refresh_token }`
3. Backend:
   - SHA256 the token, look up in `refresh_tokens` by hash
   - Verify not revoked, not expired
   - **Rotate**: revoke this refresh token, issue a new pair
4. App stores new pair, retries original request

If refresh fails → log user out, route to login screen.

### Logout
- `POST /auth/logout` revokes the current refresh token (sets `revoked_at`)
- App clears tokens from SecureStore

### Account deletion
- `DELETE /users/me` requires recent auth (token issued within last 5 min) — if not, return 403 with `code: reauth_required`
- Sets `users.deleted_at`, revokes all refresh tokens
- User's posts stay visible but author shows as "[deleted]"

## JWT details

- Algorithm: HS256
- Secret: from env `JWT_SECRET` (min 32 random bytes)
- Access token claims: `{ sub: user_id, exp, iat, role }`
- Access token TTL: 15 minutes
- Refresh token TTL: 30 days
- Refresh tokens stored hashed (never plaintext) in DB

## Mobile storage

- Both tokens → **Expo SecureStore** (uses iOS Keychain / Android Keystore)
- Never AsyncStorage
- Auth state in a Zustand store, hydrated from SecureStore on app launch

## Files to create

**Backend**
- `app/api/v1/auth.py` — route handlers
- `app/services/auth_service.py` — signup, login, verify, refresh logic
- `app/core/security.py` — JWT encode/decode, argon2 hashing, current-user dep
- `app/schemas/auth.py` — request/response models
- `app/models/refresh_token.py`, `app/models/email_verification.py`

**Frontend**
- `app/(auth)/login.tsx`
- `app/(auth)/signup.tsx`
- `app/(auth)/verify-email.tsx`
- `lib/api/auth.ts` — typed API client functions
- `store/auth.ts` — Zustand store
- `lib/hooks/useAuth.ts`
- `components/GoogleSignInButton.tsx`

## Acceptance criteria

- [ ] Can sign up with email and immediately use the app
- [ ] Email verification works (code sent, can verify)
- [ ] Can log in with Google
- [ ] Tokens persist across app restarts
- [ ] 401 triggers automatic refresh and request retry
- [ ] Logout fully clears state
- [ ] Wrong password returns generic error, not "user not found"
- [ ] Password ≥ 8 chars enforced both client and server
- [ ] All endpoints tested

## Out of scope (v1)

- Password reset via email (use Google login instead, or v2)
- 2FA
- Phone number login
- "Remember me" toggle (always remembered)
