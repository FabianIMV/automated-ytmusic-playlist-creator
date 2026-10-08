-- Credenciales de YouTube Music por usuario (headers del navegador, cifrados con Fernet).
--
-- Incluyen cookies de Google, es decir, acceso completo a la cuenta. Por eso:
--   * `data` nunca contiene texto plano: el backend lo cifra antes de escribirlo.
--   * RLS queda activado SIN políticas: ni `anon` ni `authenticated` (el frontend) pueden leer ni
--     escribir esta tabla. Solo el backend, con la clave secreta (sb_secret_... o service_role),
--     que se salta RLS. Si algún día hace falta acceso desde el frontend, se agrega una política
--     explícita; no se debe agregar una por costumbre.
--   * Además se revocan los permisos de esos roles (doble candado, por si alguien desactiva RLS).

create table if not exists public.ytmusic_credentials (
  user_id    text        primary key,  -- sub del JWT de Supabase ("local" en modo sin login)
  data       text        not null,     -- JSON de headers cifrado (token Fernet)
  updated_at timestamptz not null default now()
);

comment on table public.ytmusic_credentials is
  'Headers de YouTube Music cifrados (Fernet). Solo accesible con la clave secreta del backend.';

alter table public.ytmusic_credentials enable row level security;

revoke all on public.ytmusic_credentials from anon, authenticated;
