create table if not exists public.push_subscriptions (
  endpoint_hash text primary key,
  endpoint text not null,
  p256dh text not null,
  auth text not null,
  client_token_hash text not null,
  profile jsonb not null default '{}'::jsonb,
  seen_job_keys jsonb not null default '[]'::jsonb,
  active boolean not null default true,
  last_dispatched_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.push_subscriptions enable row level security;
revoke all on table public.push_subscriptions from anon, authenticated;
create index if not exists push_subscriptions_active_idx
  on public.push_subscriptions (active) where active=true;
