-- Funções de gatilho não devem ser expostas como RPC (/rest/v1/rpc/...).
-- O gatilho continua disparando: o PostgreSQL só exige EXECUTE ao criar o trigger.

revoke all on function public.create_post_sale_followup() from public, anon, authenticated;
revoke all on function public.schedule_prescription_review() from public, anon, authenticated;
revoke all on function public.enqueue_customer_order_whatsapp() from public, anon, authenticated;
revoke all on function public.stamp_customer_order_stage() from public, anon, authenticated;
revoke all on function public.set_customer_prescriptions_updated_at() from public, anon, authenticated;
