# Database migrations

Store reviewed SQL migrations here before applying them to Supabase.

Before production:
- Define organization/tenant ownership and access model.
- Enable restrictive RLS policies for all business data.
- Add foreign keys, unique constraints and indexes.
- Implement stock and financial changes transactionally in PostgreSQL functions.
- Keep payment-provider secrets in a trusted server-side environment, never the desktop client.

No schema is applied automatically by this repository.
