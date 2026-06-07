# Google OAuth Sign-In Troubleshooting Guide

## Problem
Google sign-in was working before but now returns users to the login page with a 401 error.

## Root Causes Identified

Based on the code analysis and deployment configuration, the most likely causes are:

### 1. **Missing or Invalid Supabase Credentials** (MOST LIKELY)
The backend requires two environment variables to verify Google OAuth tokens:
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_SERVICE_KEY` - Your Supabase service role key

**Location on VPS:** `/opt/lorevia/current/backend/.env` (or the path specified in `LOREVIA_ENV_FILE`)

**To verify:**
```bash
cd /opt/lorevia/current
grep "SUPABASE_" backend/.env
```

If these are missing or incorrect, the OAuth endpoint will fail with a 503 error: "OAuth sign-in is not configured"

### 2. **Network/Firewall Issues**
The backend needs to reach Supabase's API at `https://[your-project].supabase.co/auth/v1/user`

**To test:**
```bash
# Replace [your-supabase-url] and [your-service-key] with actual values
curl -H "apikey: [your-service-key]" \
     -H "Authorization: Bearer [test-token]" \
     "[your-supabase-url]/auth/v1/user"
```

### 3. **Email Mismatch**
The OAuth flow looks up users by:
1. First by `supabase_auth_id` (if previously linked)
2. Then by email (case-insensitive)

If your Google account email doesn't **exactly match** your LoreVia account email (after lowercasing), the lookup will fail.

### 4. **Database Connection Issues**
If the database is unreachable or the `users` table has issues.

## Changes Made

I've improved error handling and diagnostics:

### Backend (`backend/app/api/v1/routes/auth.py`)
- ✅ Added detailed logging for missing Supabase config
- ✅ Added separate timeout error handling (15 second timeout)
- ✅ Added logging for user lookup failures with email and auth ID
- ✅ Improved error messages in Supabase verification failures

### Frontend (`frontend/src/lib/auth/loginMessages.ts`)
- ✅ Added specific error messages for OAuth config issues
- ✅ Added timeout error messages
- ✅ Added 503 service unavailable handling

### Frontend Callback (`frontend/src/app/auth/callback/page.tsx`)
- ✅ Added console logging for OAuth errors (check browser DevTools)
- ✅ Logs now include session info and email for debugging

## Immediate Action Steps

### Step 1: Check Backend Logs
After attempting to sign in with Google, check the backend logs:

```bash
docker compose logs backend --tail=100 | grep -i "supabase\|oauth"
```

Look for these specific log messages:
- `supabase_oauth_config_missing` - Means env vars are missing
- `Supabase OAuth verification timed out` - Network/timeout issue
- `Supabase OAuth verification failed` - Invalid token or API error
- `supabase_oauth_no_user_found` - No account matches the Google email

### Step 2: Verify Supabase Configuration
```bash
cd /opt/lorevia/current/backend
# Check if the variables exist (without showing the actual keys)
grep -c "SUPABASE_URL" .env
grep -c "SUPABASE_SERVICE_KEY" .env
```

Both should return `1`. If they return `0`, the variables are missing.

### Step 3: Check Browser Console
1. Open browser DevTools (F12)
2. Go to Console tab
3. Attempt Google sign-in
4. Look for the error message: `OAuth sign-in failed:`
5. It will show the status code, detail, and email

### Step 4: Verify Email Match
Check what email Google is providing vs what's in your database:

From the browser console log (step 3), note the email.
Then check the database:
```sql
SELECT id, email, supabase_auth_id, email_verified_at 
FROM users 
WHERE lower(email) = '[your-google-email-lowercased]';
```

## Quick Fix Script

If Supabase credentials are missing, add them to your `.env`:

```bash
# On your VPS
cd /opt/lorevia/current/backend
nano .env

# Add these lines (replace with your actual Supabase values):
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key-here

# Save and restart
cd /opt/lorevia/current
docker compose restart backend
docker compose logs backend --tail=50
```

## Testing the Fix

After making changes:

1. Restart the backend: `docker compose restart backend`
2. Wait for health check: `docker compose exec backend python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/ready', timeout=5)"`
3. Try Google sign-in again
4. Check logs immediately after: `docker compose logs backend --tail=50 | grep -i oauth`

## Expected Log Output After Fix

**Successful OAuth:**
```
INFO: supabase_oauth_login_success user_id=... email=...
INFO: http_200 /api/v1/oauth/supabase
```

**Failed - No Config:**
```
ERROR: supabase_oauth_config_missing has_url=False has_key=False
```

**Failed - User Not Found:**
```
INFO: supabase_oauth_no_user_found supabase_auth_id=... email=...
```

## Contact Support

If none of these steps resolve the issue, collect:
1. Backend logs from Step 1
2. Browser console output from Step 3
3. Email address you're trying to sign in with
4. Whether you've successfully signed in with Google before

## Prevention

To prevent this in the future:
- Add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` to your deployment checklist
- Monitor for 503 errors on the `/api/v1/oauth/supabase` endpoint
- Set up alerts for `supabase_oauth_config_missing` log events
