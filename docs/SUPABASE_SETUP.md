# ClawOS — Supabase Setup (dummy-proof)

This guide sets up the Supabase database that ClawOS uses for license validation.  
No programming knowledge needed. Takes about 5 minutes.

---

## Step 1 — Create a free Supabase account

1. Go to **[supabase.com](https://supabase.com)**
2. Click **Start your project** → sign in with GitHub
3. Click **New project**
4. Fill in:
   - **Organization**: your name or "ClawOS"
   - **Project name**: `clawos`
   - **Database password**: generate a strong one and save it somewhere safe (you won't need it again)
   - **Region**: pick the one closest to you
5. Click **Create new project** and wait ~2 minutes for it to spin up

---

## Step 2 — Create the licenses table

1. In your new project, click **SQL Editor** in the left sidebar
2. Paste the following SQL and click **Run** (green button, bottom right):

```sql
create table if not exists licenses (
  id           uuid primary key default gen_random_uuid(),
  key          text not null unique,
  tier         text not null default 'premium',
  machine_id   text,
  email        text,
  activated_at timestamptz,
  is_active    boolean not null default true,
  created_at   timestamptz not null default now()
);

-- Index for fast key lookups
create index if not exists licenses_key_idx on licenses(key);
create index if not exists licenses_machine_idx on licenses(machine_id);
```

3. You should see **Success. No rows returned.** — that's correct.

---

## Step 3 — Get your API keys

1. Click **Settings** (gear icon) in the left sidebar → **API**
2. You'll see two values you need:

   - **Project URL** — looks like `https://xyzxyzxyz.supabase.co`
   - **anon / public key** — a long string starting with `eyJ...`

3. Copy both. Keep the **service_role** key secret — you don't need it here.

---

## Step 4 — Add the keys to ClawOS

Run these two commands on your ClawOS machine (replace the values with yours):

```bash
clawctl secret set CLAWOS_SUPABASE_URL https://xyzxyzxyz.supabase.co
clawctl secret set CLAWOS_SUPABASE_ANON_KEY eyJhbGci...your-key-here
```

Then restart the daemon:

```bash
clawctl restart
```

---

## Step 5 — Add your first license key (optional manual test)

1. Back in Supabase, click **Table Editor** → **licenses**
2. Click **Insert row**
3. Fill in:
   - `key`: `CLAW-TEST-0001-0001-0001`
   - `tier`: `premium`
   - `is_active`: `true`
   - Leave everything else blank for now
4. Click **Save**

Now test it on your ClawOS machine:

```bash
clawctl license activate CLAW-TEST-0001-0001-0001
```

You should see: `License activated. Tier: premium.`

---

## Step 6 — Issue real licenses (when selling)

When a customer pays (via Stripe, Gumroad, or manually), insert a row:

```sql
insert into licenses (key, tier, email, is_active)
values ('CLAW-XXXX-XXXX-XXXX-XXXX', 'premium', 'customer@email.com', true);
```

You can generate keys in any format matching `CLAW-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}`.

A simple generator (run once to create batches):

```python
import secrets, string

def gen_key():
    chars = string.ascii_uppercase + string.digits
    parts = [''.join(secrets.choice(chars) for _ in range(4)) for _ in range(4)]
    return 'CLAW-' + '-'.join(parts)

for _ in range(10):
    print(gen_key())
```

---

## How it works (no action needed)

When a user activates a key:

1. ClawOS calls your Supabase REST API to check the key exists and `is_active = true`
2. It writes the user's `machine_id` (a hash — not personally identifiable) to bind the key
3. The validation result is cached locally for 1 hour
4. If the user goes offline, a 72-hour grace period applies before the license degrades to Free

To transfer a license to a new machine, the user runs `clawctl license deactivate` which clears the `machine_id`.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `SUPABASE_URL not set` | Run `clawctl secret set CLAWOS_SUPABASE_URL ...` |
| `Invalid key format` | Key must be exactly `CLAW-XXXX-XXXX-XXXX-XXXX` |
| `Key not found` | Check the row exists in the licenses table with the exact same case |
| `Machine binding conflict` | Row already has a different `machine_id`. Clear it in Supabase Table Editor |
| `Connection failed` | Check your Supabase URL is correct and the project is not paused |

---

## Stripe integration (optional, when ready)

To automate key delivery after payment:

1. Create a Stripe product for $10 one-time
2. In Stripe → Webhooks, add endpoint: your server or a Supabase Edge Function
3. On `checkout.session.completed` event, generate a key and insert into the `licenses` table
4. Email the key to the customer via Resend or SendGrid

This is a separate step and not required for manual sales.
