-- ============================================================
-- LGFS Price Grid — Supabase Setup SQL
-- Run this in: Supabase Dashboard → SQL Editor → New Query
-- ============================================================

-- 1. Profiles table (extends Supabase auth.users)
create table if not exists public.profiles (
  id          uuid references auth.users on delete cascade primary key,
  email       text not null,
  full_name   text,
  role        text not null default 'Seller'
                check (role in ('Seller', 'Pricer', 'Geo Lead', 'RV Committee')),
  group_id    uuid,
  is_active   boolean not null default true,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- 2. Auto-create profile on user signup
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, email, full_name, role)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
    'Seller'
  );
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- 3. Auto-update updated_at
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end;
$$;

drop trigger if exists profiles_updated_at on public.profiles;
create trigger profiles_updated_at
  before update on public.profiles
  for each row execute procedure public.set_updated_at();

-- 4. Row Level Security
alter table public.profiles enable row level security;

-- Users can read their own profile
create policy "users_read_own" on public.profiles
  for select using (auth.uid() = id);

-- Users can update their own full_name only (not role)
create policy "users_update_own_name" on public.profiles
  for update using (auth.uid() = id)
  with check (
    role = (select role from public.profiles where id = auth.uid())
    and is_active = (select is_active from public.profiles where id = auth.uid())
  );

-- Pricer can read all profiles (for user management)
create policy "pricer_read_all" on public.profiles
  for select using (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'Pricer')
  );

-- Pricer can update all profiles (role, is_active, etc.)
create policy "pricer_update_all" on public.profiles
  for update using (
    exists (select 1 from public.profiles where id = auth.uid() and role = 'Pricer')
  );

-- 5. User Groups table
create table if not exists public.user_groups (
  id          uuid default gen_random_uuid() primary key,
  name        text not null unique,
  description text,
  created_by  uuid references public.profiles(id),
  created_at  timestamptz default now()
);

alter table public.user_groups enable row level security;

create policy "pricer_manage_groups" on public.user_groups
  using (exists (select 1 from public.profiles where id = auth.uid() and role = 'Pricer'));

create policy "all_read_groups" on public.user_groups
  for select using (auth.uid() is not null);

-- Add foreign key from profiles to groups
alter table public.profiles
  add constraint fk_group foreign key (group_id) references public.user_groups(id) on delete set null;

-- 6. Deals table (for deal history, replaces localStorage)
create table if not exists public.deals (
  id           uuid default gen_random_uuid() primary key,
  user_id      uuid references public.profiles(id) on delete set null,
  user_name    text,
  user_email   text,
  customer     text,
  country      text,
  deal_data    jsonb not null,   -- full deal snapshot
  status       text default 'draft' check (status in ('draft','submitted','approved','rejected')),
  submitted_at timestamptz,
  reviewed_by  uuid references public.profiles(id) on delete set null,
  reviewed_at  timestamptz,
  review_note  text,
  created_at   timestamptz default now(),
  updated_at   timestamptz default now()
);

alter table public.deals enable row level security;

-- Sellers see only their own deals
create policy "sellers_own_deals" on public.deals
  for all using (user_id = auth.uid());

-- Approver roles can read all deals
create policy "approvers_read_all" on public.deals
  for select using (
    exists (select 1 from public.profiles where id = auth.uid() and role in ('Pricer','Geo Lead','RV Committee'))
  );

-- Approver roles can update status/review fields
create policy "approvers_update_status" on public.deals
  for update using (
    exists (select 1 from public.profiles where id = auth.uid() and role in ('Pricer','Geo Lead','RV Committee'))
  );

drop trigger if exists deals_updated_at on public.deals;
create trigger deals_updated_at
  before update on public.deals
  for each row execute procedure public.set_updated_at();

-- 7. PDF Uploads table (Supabase Storage metadata)
create table if not exists public.pdf_uploads (
  id            uuid default gen_random_uuid() primary key,
  user_id       uuid references public.profiles(id) on delete set null,
  deal_id       uuid references public.deals(id) on delete cascade,
  file_name     text not null,
  storage_path  text not null,   -- path in Supabase Storage bucket
  file_size     integer,
  uploaded_at   timestamptz default now()
);

alter table public.pdf_uploads enable row level security;

create policy "users_own_pdfs" on public.pdf_uploads
  for all using (user_id = auth.uid());

create policy "approvers_read_pdfs" on public.pdf_uploads
  for select using (
    exists (select 1 from public.profiles where id = auth.uid() and role in ('Pricer','Geo Lead','RV Committee'))
  );

-- 8. Storage bucket for PDFs
-- Run this separately or via Dashboard → Storage → New Bucket
-- insert into storage.buckets (id, name, public) values ('quote-pdfs', 'quote-pdfs', false);

-- ============================================================
-- AFTER RUNNING: go to Supabase Dashboard →
--   Authentication → Settings → set Site URL to your Netlify URL
--   Authentication → Email Templates → update confirm/reset email templates
-- ============================================================
