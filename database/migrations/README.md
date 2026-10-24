# Supabase migrations

Execute os arquivos SQL desta pasta no SQL Editor do projeto Supabase, em ordem alfabética.

## Produtos — 202610240001_products.sql

A migration cria as tabelas `organizations`, `organization_members` e `products`, índices para pesquisa e unicidade, controle de atualização e políticas RLS para separar os dados por organização. O cliente desktop usa somente a chave pública/publishable do projeto; nunca use `service_role` no aplicativo.

Após aplicar a migration, crie uma linha em `organizations` para a ótica e vincule o usuário que já pode autenticar em `organization_members`, usando o UUID de `auth.users`. O usuário precisa ter uma associação ativa para carregar e editar o catálogo. Faça esse provisionamento administrativo pelo Supabase, nunca por uma chave privilegiada embutida no aplicativo.

O modo `python app.py --preview` usa armazenamento temporário em memória e não grava dados no Supabase. Os dados inseridos nessa pré-visualização são descartados ao fechar o aplicativo.
