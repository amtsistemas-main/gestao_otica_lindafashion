-- Supporting indexes for foreign keys and fixed search_path for the products timestamp trigger.
create index if not exists purchase_request_items_org_idx
    on public.purchase_request_items(organization_id);
create index if not exists purchase_request_items_product_idx
    on public.purchase_request_items(product_id);
create index if not exists purchase_requests_created_by_idx
    on public.purchase_requests(created_by);
create index if not exists purchase_requests_supplier_idx
    on public.purchase_requests(supplier_id);
create index if not exists stock_movements_created_by_idx
    on public.stock_movements(created_by);

alter function public.set_products_updated_at() set search_path = public;
