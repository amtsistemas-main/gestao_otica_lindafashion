alter table public.products
    add column if not exists image_url text not null default '';

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('product-images', 'product-images', true, 8388608, array['image/png', 'image/jpeg', 'image/webp'])
on conflict (id) do update
set public = excluded.public,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Product images are publicly readable" on storage.objects;
create policy "Product images are publicly readable"
on storage.objects for select
to public
using (bucket_id = 'product-images');

drop policy if exists "Organization members upload product images" on storage.objects;
create policy "Organization members upload product images"
on storage.objects for insert
to authenticated
with check (
    bucket_id = 'product-images'
    and (storage.foldername(name))[1] in (
        select om.organization_id::text
        from public.organization_members om
        where om.user_id = (select auth.uid())
          and om.active = true
    )
);

drop policy if exists "Organization members update product images" on storage.objects;
create policy "Organization members update product images"
on storage.objects for update
to authenticated
using (
    bucket_id = 'product-images'
    and (storage.foldername(name))[1] in (
        select om.organization_id::text
        from public.organization_members om
        where om.user_id = (select auth.uid())
          and om.active = true
    )
)
with check (
    bucket_id = 'product-images'
    and (storage.foldername(name))[1] in (
        select om.organization_id::text
        from public.organization_members om
        where om.user_id = (select auth.uid())
          and om.active = true
    )
);

drop policy if exists "Organization members delete product images" on storage.objects;
create policy "Organization members delete product images"
on storage.objects for delete
to authenticated
using (
    bucket_id = 'product-images'
    and (storage.foldername(name))[1] in (
        select om.organization_id::text
        from public.organization_members om
        where om.user_id = (select auth.uid())
          and om.active = true
    )
);
