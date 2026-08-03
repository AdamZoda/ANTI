-- ═══════════════════════════════════════════════════════════════════════════
-- 🛡️ ANTI — COLONNE "ÉMIS PAR" + DIAGNOSTIC DES SCANS INVISIBLES
-- ═══════════════════════════════════════════════════════════════════════════
-- À exécuter dans Supabase → SQL Editor
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 1. Ajouter la colonne created_by_username sur scans (pour le NOUVEAU build EXE) ───
ALTER TABLE public.scans ADD COLUMN IF NOT EXISTS created_by_username character varying;

-- ─── 2. Backfill : remplir le nom du support/admin pour les scans EXISTANTS ───
UPDATE public.scans s
SET created_by_username = a.discord_username
FROM public.admins a
WHERE s.created_by_discord_id IS NOT NULL
  AND s.created_by_username IS NULL
  AND a.discord_id = s.created_by_discord_id;

-- ─── 3. DIAGNOSTIC : répartition des scans par server_key ───
SELECT COALESCE(server_key, '(NULL)') AS server_key,
       COUNT(*) AS nb_scans,
       COUNT(DISTINCT pin_code) AS nb_pins,
       COUNT(DISTINCT created_by_discord_id) AS nb_support
FROM public.scans
GROUP BY server_key
ORDER BY nb_scans DESC;

-- ─── 4. DIAGNOSTIC : scans dont le server_key ne correspond à AUCUN serveur enregistré ───
--     (c'est la cause la plus probable des scans "invisibles" : PIN créé sans server_key)
SELECT s.scan_id, s.timestamp, s.hwid, s.pin_code, s.created_by_discord_id, s.server_key
FROM public.scans s
LEFT JOIN public.servers sv ON sv.server_key = s.server_key
WHERE sv.server_key IS NULL
ORDER BY s.timestamp DESC
LIMIT 100;

-- ─── 5. RÉPARATION : recoller les scans orphelins (server_key NULL ou 'default')
--     vers le serveur MAJESTIC (srv_dc_492135...) — À ADAPTER à TON contexte.
-- UPDATE public.scans
-- SET server_key = 'srv_dc_492135...'
-- WHERE server_key IS NULL OR server_key = 'default';

-- ─── 6. VÉRIFICATION finale : les 20 derniers scans avec leur émetteur + PIN ───
SELECT scan_id, timestamp, hwid, pin_code, created_by_username, created_by_discord_id, server_key
FROM public.scans
ORDER BY timestamp DESC
LIMIT 20;