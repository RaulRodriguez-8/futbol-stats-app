-- tabla partidos
create table if not exists partidos (
  id bigserial primary key,
  nombre text,
  local text,
  visitante text,
  competicion text,
  fecha date
);

-- tabla eventos
create table if not exists eventos (
  id bigserial primary key,
  partido_id bigint references partidos(id) on delete cascade,
  equipo text check (equipo in ('Local','Visitante')),
  accion text,
  parte text,
  minuto int,
  timestamp timestamptz default now()
);
