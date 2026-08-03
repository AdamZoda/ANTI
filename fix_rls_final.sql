-- ═══════════════════════════════════════════════════════════════════════════
-- 🛡️ ANTI — FACTORY RESET RLS : ISOLATION STRICTE PAR RÔLE (FINAL)
-- ═══════════════════════════════════════════════════════════════════════════
-- À exécuter en UNE FOIS dans Supabase → SQL Editor (rôle postgres/service_role).
--
-- RÈGLES MÉTIER APPLIQUÉES CÔTÉ BASE DE DONNÉES :
--   • super_admin (global) → VOIT TOUT (GLOBAL : tous les scans de tous les serveurs)
--   • admin / server_owner  → voit TOUS les scans de SON serveur seulement
--   • support               → voit les scans qu'IL a générés (created_by_discord_id = lui),
--                             uniquement sur son serveur
--   • EXE (rôle anon)       → consomme les PINs + écrit les scans (fonctionnement du client)
-- ═══════════════════════════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════════════
-- FONCTIONS AIDES (SECURITY DEFINER => pas de récursion RLS)
-- ═══════════════════════════════════════════════════════════════

-- Retourne le Discord ID de l'utilisateur connecté (Extrait du JWT Discord OAuth)
CREATE OR REPLACE FUNCTION public.current_discord_id()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT (auth.jwt() -> 'user_metadata' ->> 'provider_id');
$$;

-- Retourne le rôle (prioritaire) de l'utilisateur connecté pour un serveur donné.
-- - super_admin toujours retourné (global)
-- - sinon le rôle admin / support s'il a une entrée sur ce serveur
CREATE OR REPLACE FUNCTION public.user_role_for_server(p_server_key text)
RETURNS text
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT a.role
  FROM public.admins a
  WHERE a.discord_id = public.current_discord_id()
    AND (a.server_key = p_server_key OR a.role = 'super_admin')
  ORDER BY CASE a.role
             WHEN 'super_admin' THEN 0
             WHEN 'admin'        THEN 1
             WHEN 'server_owner' THEN 1
             WHEN 'owner'        THEN 1
             ELSE 2
           END
  LIMIT 1;
$$;

-- ═══════════════════════════════════════════════════════════════
-- ACTIVATION RLS SUR TOUTES LES TABLES
-- ═══════════════════════════════════════════════════════════════
ALTER TABLE public.scans            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scan_pins        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.servers          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.admins           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.discord_profiles ENABLE ROW LEVEL SECURITY;

-- ═══════════════════════════════════════════════════════════════
-- SCANS
-- ═══════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS "scans_role_select"  ON public.scans;
DROP POLICY IF EXISTS "scans_anon_select"  ON public.scans;
DROP POLICY IF EXISTS "scans_anon_insert"  ON public.scans;
DROP POLICY IF EXISTS "scans_anon_update"  ON public.scans;
DROP POLICY IF EXISTS "Allow authenticated reads" ON public.scans;
DROP POLICY IF EXISTS "Allow anon insert" ON public.scans;
DROP POLICY IF EXISTS "Allow anon update" ON public.scans;
-- Anciennes policies résiduelles (rôle public = anon + authenticated) à supprimer
DROP POLICY IF EXISTS "Allow public read access" ON public.scans;
DROP POLICY IF EXISTS "Allow public insert access" ON public.scans;
DROP POLICY IF EXISTS "Permettre la lecture publique/admin des scans" ON public.scans;
DROP POLICY IF EXISTS "Permettre l'insertion publique des scans" ON public.scans;

-- Panel (authenticated) : lecture selon le rôle
CREATE POLICY "scans_role_select" ON public.scans
FOR SELECT TO authenticated
USING (
  public.current_discord_id() IS NOT NULL
  AND (
    -- super_admin (global) OU admin du serveur -> tout le serveur
    public.user_role_for_server(scans.server_key)
      IN ('super_admin','admin','server_owner','owner')
    -- support : uniquement les scans qu'il a lui-même générés (via son PIN)
    OR scans.created_by_discord_id = public.current_discord_id()
  )
);

-- EXE client (anon) : écriture + lecture (génération scan_id)
CREATE POLICY "scans_anon_select" ON public.scans FOR SELECT TO anon USING (true);
CREATE POLICY "scans_anon_insert" ON public.scans FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "scans_anon_update" ON public.scans FOR UPDATE TO anon USING (true);

-- ═══════════════════════════════════════════════════════════════
-- SCAN_PINS
-- ═══════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS "pins_role_select" ON public.scan_pins;
DROP POLICY IF EXISTS "pins_role_insert" ON public.scan_pins;
DROP POLICY IF EXISTS "pins_anon_select" ON public.scan_pins;
DROP POLICY IF EXISTS "pins_anon_update" ON public.scan_pins;
DROP POLICY IF EXISTS "Allow authenticated reads pins" ON public.scan_pins;
DROP POLICY IF EXISTS "Allow authenticated insert pins" ON public.scan_pins;
DROP POLICY IF EXISTS "Allow authenticated update pins" ON public.scan_pins;
DROP POLICY IF EXISTS "Allow anon reads pins" ON public.scan_pins;
DROP POLICY IF EXISTS "Allow anon update pins" ON public.scan_pins;

-- Panel (authenticated) : lecture PAR RÔLE
CREATE POLICY "pins_role_select" ON public.scan_pins FOR SELECT TO authenticated
USING (
  public.current_discord_id() IS NOT NULL
  AND (
      public.user_role_for_server(scan_pins.server_key)
        IN ('super_admin','admin','server_owner','owner')
      OR scan_pins.created_by_discord_id = public.current_discord_id()
  )
);

-- Panel (authenticated) : un staff (admin ou support) crée un PIN sur SON serveur
CREATE POLICY "pins_role_insert" ON public.scan_pins FOR INSERT TO authenticated
WITH CHECK (
  public.current_discord_id() IS NOT NULL
  AND public.user_role_for_server(scan_pins.server_key) IS NOT NULL
);

-- EXE (anon) : lire + consommer les PINs
CREATE POLICY "pins_anon_select" ON public.scan_pins FOR SELECT TO anon USING (true);
CREATE POLICY "pins_anon_update" ON public.scan_pins FOR UPDATE TO anon USING (true);

-- ═══════════════════════════════════════════════════════════════
-- SERVERS
-- ═══════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS "servers_select"      ON public.servers;
DROP POLICY IF EXISTS "servers_sa_write"    ON public.servers;
DROP POLICY IF EXISTS "servers_anon_select" ON public.servers;
DROP POLICY IF EXISTS "Allow authenticated reads servers" ON public.servers;
DROP POLICY IF EXISTS "Allow authenticated write servers" ON public.servers;
DROP POLICY IF EXISTS "Allow anon reads servers" ON public.servers;

-- Panel + EXE (lecture)
CREATE POLICY "servers_select"      ON public.servers FOR SELECT TO authenticated USING (true);
CREATE POLICY "servers_anon_select" ON public.servers FOR SELECT TO anon USING (true);

-- Création / gestion serveur : super_admin UNIQUEMENT
CREATE POLICY "servers_sa_write" ON public.servers
FOR ALL TO authenticated
USING (public.current_discord_id() IS NOT NULL
       AND public.user_role_for_server(servers.server_key) = 'super_admin')
WITH CHECK (public.current_discord_id() IS NOT NULL
           AND public.user_role_for_server(servers.server_key) = 'super_admin');

-- ═══════════════════════════════════════════════════════════════
-- ADMINS  (gestion de l'équipe)
-- ═══════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS "admins_select"      ON public.admins;
DROP POLICY IF EXISTS "admins_insert"      ON public.admins;
DROP POLICY IF EXISTS "admins_update"      ON public.admins;
DROP POLICY IF EXISTS "admins_delete"      ON public.admins;
DROP POLICY IF EXISTS "Allow authenticated reads admins" ON public.admins;
DROP POLICY IF EXISTS "Allow authenticated write admins" ON public.admins;
-- Anciennes policies par défaut Supabase (publiques et dangereuses) à supprimer
DROP POLICY IF EXISTS "Allow anon reads admins" ON public.admins;
DROP POLICY IF EXISTS "Authenticated users can read admins" ON public.admins;
DROP POLICY IF EXISTS "Authenticated users can insert admins" ON public.admins;
DROP POLICY IF EXISTS "Authenticated users can delete admins" ON public.admins;

-- Lecture : tous les connectés (liste du staff)
CREATE POLICY "admins_select" ON public.admins FOR SELECT TO authenticated USING (true);

-- Insertion : super_admin OU un admin ajoutant du support sur SON serveur
CREATE POLICY "admins_insert" ON public.admins FOR INSERT TO authenticated
WITH CHECK (
  public.user_role_for_server(admins.server_key) = 'super_admin'
  OR (
      public.user_role_for_server(admins.server_key) IN ('admin','server_owner','owner')
      AND admins.role = 'support'
  )
);

-- Mise à jour : l'utilisateur met à jour sa propre ligne OU super_admin modifie chacun
CREATE POLICY "admins_update" ON public.admins FOR UPDATE TO authenticated
USING (
  admins.discord_id = public.current_discord_id()
  OR public.user_role_for_server(admins.server_key) = 'super_admin'
);

-- Suppression : super_admin UNIQUEMENT
CREATE POLICY "admins_delete" ON public.admins FOR DELETE TO authenticated
USING (public.user_role_for_server(admins.server_key) = 'super_admin');

-- ═══════════════════════════════════════════════════════════════
-- DISCORD_PROFILES
-- ═══════════════════════════════════════════════════════════════
DROP POLICY IF EXISTS "profiles_select" ON public.discord_profiles;
DROP POLICY IF EXISTS "profiles_write"  ON public.discord_profiles;
DROP POLICY IF EXISTS "profiles_update" ON public.discord_profiles;
DROP POLICY IF EXISTS "Allow authenticated reads discord_profiles" ON public.discord_profiles;
DROP POLICY IF EXISTS "Allow authenticated write discord_profiles" ON public.discord_profiles;

-- Lecture : les connectés (pour chercher un profil lors de l'ajout au staff)
CREATE POLICY "profiles_select" ON public.discord_profiles FOR SELECT TO authenticated USING (true);

-- Écriture sur le profil de l'utilisateur au login (upsert)
CREATE POLICY "profiles_write" ON public.discord_profiles FOR INSERT TO authenticated
WITH CHECK (public.current_discord_id() IS NOT NULL);

CREATE POLICY "profiles_update" ON public.discord_profiles FOR UPDATE TO authenticated
USING (discord_id = public.current_discord_id()
       OR public.user_role_for_server(NULL) = 'super_admin');

-- ═══════════════════════════════════════════════════════════════
-- VÉRIFICATION FINALE
-- ═══════════════════════════════════════════════════════════════
SELECT policyname, roles, cmd, qual
FROM pg_policies
WHERE schemaname = 'public'
ORDER BY tablename, policyname;

-- ⚠️ RÉELLEMENT DANGEREUX : toute policy avec roles = {public}
--    (public = anon + authenticated => affecte aussi le panel).
--    La liste ci-dessous DOIT être vide après exécution.
SELECT 'DANGER' AS statut, tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND roles && ARRAY['public']::name[]
ORDER BY tablename, policyname;

-- ✅ NORMAL (à conserver) : policies EXE client (clé anon) nécessaires au fonctionnement du scanneur.
--    anon = droits du client qui consomme les PINs et écrit les scans.
SELECT 'OK_EXE' AS statut, tablename, policyname, roles, cmd
FROM pg_policies
WHERE schemaname = 'public'
  AND roles && ARRAY['anon']::name[]
ORDER BY tablename, policyname;