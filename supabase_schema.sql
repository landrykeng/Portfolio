-- ============================================================
--  My portfolio : schéma Supabase
--  À exécuter dans Supabase > SQL Editor > New query > Run
-- ============================================================

-- 1. Catégories (liste gérée depuis l'onglet Réglages)
create table if not exists public.categories (
    id          bigint generated always as identity primary key,
    nom         text not null check (length(trim(nom)) > 0),
    created_at  timestamptz not null default now()
);

-- Unicité insensible à la casse : « Transport » et « transport » sont identiques
create unique index if not exists categories_nom_unique
    on public.categories (lower(nom));

-- 2. Opérations (dépenses et ressources)
create table if not exists public.operations (
    id             bigint generated always as identity primary key,
    date           date not null default current_date,
    nature         text not null check (nature in ('Dépense', 'Ressource')),
    categorie_id   bigint not null
                   references public.categories (id) on delete restrict,
    date_echeance  date,
    libelle        text not null check (length(trim(libelle)) > 0),
    montant        numeric(14, 2) not null check (montant > 0),
    created_at     timestamptz not null default now()
);

create index if not exists operations_date_idx      on public.operations (date desc);
create index if not exists operations_categorie_idx on public.operations (categorie_id);
create index if not exists operations_echeance_idx  on public.operations (date_echeance)
    where date_echeance is not null;

-- 3. Sécurité : RLS activée et aucune politique publique.
--    Seule la clé « service_role » (utilisée côté serveur par Streamlit) peut lire/écrire.
alter table public.categories enable row level security;
alter table public.operations enable row level security;

-- 4. Catégories de départ
insert into public.categories (nom) values
    ('Transport'), ('Alimentation'), ('Connexion'), ('Emprunt'), ('Prêt'), ('Aide'),
    ('Fourniture'), ('Service'), ('Bien de base'), ('Salaire'), ('Autre')
on conflict do nothing;
