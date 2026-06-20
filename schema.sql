create table projects (
  id uuid primary key default gen_random_uuid(),
  nome text not null,
  objetivo text,
  tipo text not null default 'pessoal' check (tipo in ('freelance', 'pessoal')),
  created_at timestamptz default now()
);

create table tasks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid references projects(id) on delete cascade,
  descricao text not null,
  done boolean default false,
  created_at timestamptz default now()
);