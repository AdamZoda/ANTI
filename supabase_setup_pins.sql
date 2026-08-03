-- ─────────────────────────────────────────────────────────────
-- 🛡️ ANTI DEFENSE SYSTEM — NETTOYAGE COMPLET & SETUP SERVEUR ATC
-- Exécute ce script dans l'éditeur SQL de Supabase (SQL Editor)
-- ⚠️ ATTENTION : Ce script SUPPRIME les admins non-super et relie tout à ATC
-- ─────────────────────────────────────────────────────────────

-- ═══════════════════════════════════════════════════════════
-- ÉTAPE 1 : Créer les tables manquantes
-- ═══════════════════════════════════════════════════════════

-- Table Serveurs RP
CREATE TABLE IF NOT EXISTS public.servers (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  server_key character varying NOT NULL UNIQUE,
  server_prefix character varying(3),
  name character varying NOT NULL,
  owner_discord_id character varying,
  owner_name character varying,
  max_pins_quota integer NOT NULL DEFAULT 0,
  invite_url character varying,
  status character varying NOT NULL DEFAULT 'ACTIVE',
  subscription_expires_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now()
);

-- Colonnes manquantes sur servers (si la table existait déjà)
ALTER TABLE public.servers ADD COLUMN IF NOT EXISTS server_prefix character varying(3);
ALTER TABLE public.servers ADD COLUMN IF NOT EXISTS owner_name character varying;
ALTER TABLE public.servers ADD COLUMN IF NOT EXISTS max_pins_quota integer DEFAULT 0;
ALTER TABLE public.servers ADD COLUMN IF NOT EXISTS invite_url character varying;
ALTER TABLE public.servers ADD COLUMN IF NOT EXISTS status character varying DEFAULT 'ACTIVE';
ALTER TABLE public.servers ADD COLUMN IF NOT EXISTS subscription_expires_at timestamp with time zone;

-- Table Profils Discord (collectés au login)
CREATE TABLE IF NOT EXISTS public.discord_profiles (
  discord_id character varying PRIMARY KEY,
  username character varying NOT NULL,
  avatar_url character varying,
  email character varying,
  user_guilds jsonb DEFAULT '[]'::jsonb,
  last_login_at timestamp with time zone DEFAULT now()
);
ALTER TABLE public.discord_profiles ADD COLUMN IF NOT EXISTS user_guilds jsonb DEFAULT '[]'::jsonb;

-- 🔓 ACCRÉDITATIONS & PERMISSIONS (Élimination des erreurs 403)
ALTER TABLE public.servers DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.discord_profiles DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.scan_pins DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.admins DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.scans DISABLE ROW LEVEL SECURITY;

GRANT ALL ON public.servers TO anon, authenticated, service_role;
GRANT ALL ON public.discord_profiles TO anon, authenticated, service_role;
GRANT ALL ON public.scan_pins TO anon, authenticated, service_role;
GRANT ALL ON public.admins TO anon, authenticated, service_role;
GRANT ALL ON public.scans TO anon, authenticated, service_role;

-- Table PINs de scan
CREATE TABLE IF NOT EXISTS public.scan_pins (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  pin_code character varying(10) NOT NULL UNIQUE,
  created_by_discord_id character varying NOT NULL,
  created_by_username character varying,
  server_key character varying NOT NULL DEFAULT 'atc',
  status character varying NOT NULL DEFAULT 'PENDING',
  created_at timestamp with time zone DEFAULT now(),
  expires_at timestamp with time zone NOT NULL,
  used_at timestamp with time zone,
  used_hwid character varying
);

-- Colonnes manquantes sur admins
ALTER TABLE public.admins ADD COLUMN IF NOT EXISTS role character varying DEFAULT 'support';
ALTER TABLE public.admins ADD COLUMN IF NOT EXISTS server_key character varying DEFAULT 'atc';
ALTER TABLE public.admins ADD COLUMN IF NOT EXISTS server_name character varying DEFAULT 'ATC';
ALTER TABLE public.admins ADD COLUMN IF NOT EXISTS email character varying;
ALTER TABLE public.admins ADD COLUMN IF NOT EXISTS last_login_at timestamp with time zone;
ALTER TABLE public.admins ADD COLUMN IF NOT EXISTS created_by_discord_id character varying;

-- Colonnes manquantes sur scans
ALTER TABLE public.scans ADD COLUMN IF NOT EXISTS pin_code character varying(10);
ALTER TABLE public.scans ADD COLUMN IF NOT EXISTS created_by_discord_id character varying;
ALTER TABLE public.scans ADD COLUMN IF NOT EXISTS server_key character varying DEFAULT 'atc';

-- Index
CREATE INDEX IF NOT EXISTS idx_scan_pins_code ON public.scan_pins(pin_code);
CREATE INDEX IF NOT EXISTS idx_scan_pins_server ON public.scan_pins(server_key);

-- ═══════════════════════════════════════════════════════════
-- ÉTAPE 2 : Créer le serveur ATC
-- ═══════════════════════════════════════════════════════════

INSERT INTO public.servers (server_key, server_prefix, name, owner_discord_id, owner_name, max_pins_quota, status)
VALUES ('atc', 'AT', 'ATC', '759495908370022421', 'super admin v2', 0, 'ACTIVE')
ON CONFLICT (server_key) DO NOTHING;

-- ═══════════════════════════════════════════════════════════
-- ÉTAPE 3 : Lier TOUS les scans existants au serveur ATC
-- ═══════════════════════════════════════════════════════════

UPDATE public.scans SET server_key = 'atc' WHERE server_key IS NULL OR server_key = 'default';

-- ═══════════════════════════════════════════════════════════
-- ÉTAPE 4 : Nettoyage des admins — ne garder que le Super Admin
-- ═══════════════════════════════════════════════════════════

-- Supprimer TOUS les admins sauf le super admin (discord_id = '759495908370022421')
DELETE FROM public.admins WHERE discord_id != '759495908370022421';

-- Mettre à jour le super admin pour le lier à ATC
UPDATE public.admins 
SET role = 'super_admin', server_key = 'atc', server_name = 'ATC'
WHERE discord_id = '759495908370022421';

-- ═══════════════════════════════════════════════════════════
-- VÉRIFICATION — Exécute ces requêtes pour vérifier
-- ═══════════════════════════════════════════════════════════

-- SELECT * FROM public.servers;
-- SELECT * FROM public.admins;
-- SELECT count(*), server_key FROM public.scans GROUP BY server_key;
