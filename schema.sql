-- ===============================
-- TABLA PARTIDOS
-- ===============================
create table if not exists partidos (
  id bigserial primary key,
  nombre text,
  local text,
  visitante text,
  competicion text,
  jornada text,
  lugar text,
  fecha date
);

-- ===============================
-- TABLA EVENTOS
-- ===============================
create table if not exists eventos (
  id bigserial primary key,
  partido_id bigint references partidos(id) on delete cascade,
  equipo text,
  accion text,
  parte text,
  minuto int,
  tiempo_exact text,
  timestamp timestamptz default now()
);
