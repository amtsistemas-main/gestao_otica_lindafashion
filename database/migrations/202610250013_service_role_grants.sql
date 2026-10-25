-- As Edge Functions (admin-users, whatsapp-*) usam a chave de serviço do servidor, que
-- ignora o RLS mas ainda precisa de privilégio nas tabelas. Neste projeto as tabelas não
-- eram concedidas automaticamente ao service_role, então as funções liam "nada" e
-- respondiam "Usuário sem vínculo ativo com esta organização".
-- O service_role existe somente no servidor (nunca no app desktop).

grant usage on schema public to service_role;
grant all on all tables in schema public to service_role;
grant all on all sequences in schema public to service_role;

-- Tabelas e sequências criadas daqui em diante (pelo dono das migrations) também.
alter default privileges for role postgres in schema public grant all on tables to service_role;
alter default privileges for role postgres in schema public grant all on sequences to service_role;
