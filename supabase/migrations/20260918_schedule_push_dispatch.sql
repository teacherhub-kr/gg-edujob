create extension if not exists pg_net with schema extensions;
create extension if not exists pg_cron;

alter table public.edujob_alert_config
  add column if not exists last_dispatch_request_id bigint,
  add column if not exists last_dispatch_requested_at timestamptz;

create schema if not exists edujob_private;
revoke all on schema edujob_private from public;
revoke all on schema edujob_private from anon;
revoke all on schema edujob_private from authenticated;

create or replace function edujob_private.invoke_push_dispatch()
returns bigint
language plpgsql
security definer
set search_path = ''
as $$
declare
  v_secret text;
  v_request_id bigint;
begin
  select dispatch_secret
    into v_secret
  from public.edujob_alert_config
  where id = 1;

  if v_secret is null or length(v_secret) < 32 then
    raise exception 'dispatch secret unavailable';
  end if;

  select net.http_post(
    url := 'https://ahghkusvbfwrdmrhkgwe.supabase.co/functions/v1/push-dispatch',
    headers := jsonb_build_object(
      'content-type', 'application/json',
      'x-edujob-alert-secret', v_secret
    ),
    body := '{}'::jsonb,
    timeout_milliseconds := 120000
  )
  into v_request_id;

  update public.edujob_alert_config
  set last_dispatch_request_id = v_request_id,
      last_dispatch_requested_at = now(),
      updated_at = now()
  where id = 1;

  return v_request_id;
end;
$$;

revoke all on function edujob_private.invoke_push_dispatch() from public;
revoke all on function edujob_private.invoke_push_dispatch() from anon;
revoke all on function edujob_private.invoke_push_dispatch() from authenticated;

do $$
declare
  v_jobid bigint;
begin
  select jobid into v_jobid
  from cron.job
  where jobname = 'edujob-push-dispatch'
  limit 1;

  if v_jobid is not null then
    perform cron.unschedule(v_jobid);
  end if;

  perform cron.schedule(
    'edujob-push-dispatch',
    '*/15 * * * *',
    'select edujob_private.invoke_push_dispatch();'
  );
end;
$$;
