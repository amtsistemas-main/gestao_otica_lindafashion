# Supabase migrations

Execute os arquivos SQL desta pasta no SQL Editor do projeto Supabase, em ordem alfabética.

## Produtos — 202610240001_products.sql

A migration cria as tabelas `organizations`, `organization_members` e `products`, índices para pesquisa e unicidade, controle de atualização e políticas RLS para separar os dados por organização. O cliente desktop usa somente a chave pública/publishable do projeto; nunca use `service_role` no aplicativo.

### Provisionar a primeira organização

Depois de executar a migration, crie a organização no SQL Editor e copie o UUID retornado:

```sql
insert into public.organizations (name)
values ('Ótica Linda Fashion')
returning id;
```

Localize o UUID do usuário que já consegue entrar pelo Supabase Auth (Dashboard → Authentication → Users). Em seguida, substitua os dois valores de exemplo e execute:

```sql
insert into public.organization_members (organization_id, user_id, role, active)
values (
    'COLE_AQUI_O_UUID_DA_ORGANIZACAO'::uuid,
    'COLE_AQUI_O_UUID_DO_USUARIO_AUTH'::uuid,
    'owner',
    true
);
```

Faça esse provisionamento administrativo pelo Supabase, nunca por uma chave privilegiada embutida no aplicativo. O usuário precisa ter uma associação ativa para carregar e editar o catálogo.

O modo `python app.py --preview` usa armazenamento temporário em memória e não grava dados no Supabase. Os dados inseridos nessa pré-visualização são descartados ao fechar o aplicativo.
