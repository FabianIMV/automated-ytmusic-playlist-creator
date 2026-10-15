-- Función mínima para mantener activo el proyecto de Supabase.
--
-- En el plan gratuito, Supabase pausa los proyectos que pasan 7 días sin actividad en la base.
-- El workflow .github/workflows/supabase-keepalive.yml la llama cada 3 días vía
-- POST /rest/v1/rpc/keepalive con la publishable key, lo que ejecuta una consulta real.
-- No lee ni escribe ninguna tabla: solo devuelve la hora del servidor.

create or replace function public.keepalive()
returns timestamptz
language sql
stable
security invoker
set search_path = ''
as $$ select now() $$;

revoke all on function public.keepalive() from public;
grant execute on function public.keepalive() to anon, authenticated;

comment on function public.keepalive() is
  'Ping para que el proyecto free no se pause por inactividad (ver workflow supabase-keepalive).';
