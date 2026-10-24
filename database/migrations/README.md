# Supabase migrations and local connection

The application is configured for the Ótica Linda Fashion Supabase project:
`https://swlccwcykxmvwptzxrxt.supabase.co`.

## Configure the desktop application

1. Copy `.env.example` to `.env` in the project root.
2. In the Supabase Dashboard for this project, open **Connect** or **Settings → API Keys** and copy the **publishable** key (usually starts with `sb_publishable_`). A legacy `anon` key is also a public client key if the project has not created publishable keys yet.
3. Paste that value into `SUPABASE_PUBLISHABLE_KEY` in your local `.env`.
4. Restart the application. Do not commit `.env` and never use a `service_role` or secret key in this desktop application.

The project URL is configured as a safe default in `config/settings.py`; it can still be overridden through `SUPABASE_URL`.

## Products — `202610240001_products.sql`

Before applying this migration, inspect the target project's actual schema and migration history to avoid conflicting with existing tables. Execute SQL migrations in this directory in order only after confirming they are needed.

The migration creates `organizations`, `organization_members` and `products`, indexes, an update trigger and organization-scoped RLS policies. The desktop client uses only a public/publishable key; database RLS is the authorization boundary.

### Provision the first organization

After confirming the migration is installed, create the organization in the SQL Editor and copy the returned UUID:

```sql
insert into public.organizations (name)
values ('Ótica Linda Fashion')
returning id;
```

Locate the UUID of the user created in Supabase Auth (Dashboard → Authentication → Users). Replace the two example values and execute:

```sql
insert into public.organization_members (organization_id, user_id, role, active)
values (
    'COLE_AQUI_O_UUID_DA_ORGANIZACAO'::uuid,
    'COLE_AQUI_O_UUID_DO_USUARIO_AUTH'::uuid,
    'owner',
    true
);
```

Perform this administrative provisioning in the Supabase Dashboard, never from the desktop app with a privileged key. The user needs an active organization membership to load and edit the product catalog.

The `python app.py --preview` mode uses temporary in-memory storage and never writes to Supabase. Preview data is discarded when the app closes.
