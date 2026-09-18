create extension if not exists pgcrypto;

create table if not exists public.edujob_push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  endpoint_hash text not null unique,
  endpoint text not null,
  p256dh text not null,
  auth text not null,
  client_token_hash text not null,
  profile jsonb not null default '{}'::jsonb,
  seen_ids jsonb not null default '[]'::jsonb,
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_notified_at timestamptz
);

create index if not exists edujob_push_subscriptions_enabled_idx
  on public.edujob_push_subscriptions (enabled)
  where enabled = true;

alter table public.edujob_push_subscriptions enable row level security;

revoke all on table public.edujob_push_subscriptions from public;
revoke all on table public.edujob_push_subscriptions from anon;
revoke all on table public.edujob_push_subscriptions from authenticated;

comment on table public.edujob_push_subscriptions is
  'Anonymous Web Push subscriptions for 수도권에듀잡. Access only through Edge Functions using service role.';
