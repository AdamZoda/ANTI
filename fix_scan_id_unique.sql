-- ═══════════════════════════════════════════════════════════════════════════
-- 🛡️ ANTI — FIX CRITIQUE : UNIQUE scan_id + colonne support + backfill
-- ═══════════════════════════════════════════════════════════════════════════
-- Exécuter dans Supabase → SQL Editor (UNE SEULE FOIS)
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 1. CRITIQUE : Contrainte UNIQUE sur scan_id ─────────────────────────
--     SANS CELA, le PostgREST "resolution=merge-duplicates" échoue silencieusement
--     et les scans ne sont jamais insérés dans la base.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.scans'::regclass
      AND contype IN ('u', 'p')
      AND conkey @> ARRAY[
        (SELECT attnum FROM pg_attribute WHERE attrelid = 'public.scans'::regclass AND attname = 'scan_id')
      ]
  ) THEN
    ALTER TABLE public.scans ADD CONSTRAINT scans_scan_id_unique UNIQUE (scan_id);
    RAISE NOTICE '✅ Contrainte UNIQUE ajoutée sur scans.scan_id';
  ELSE
    RAISE NOTICE 'ℹ️  Contrainte UNIQUE/PRIMARY sur scan_id existe déjà';
  END IF;
END $$;

-- ─── 2. Colonne created_by_username (pour afficher "Émis par" dans le dashboard) ───
ALTER TABLE public.scans ADD COLUMN IF NOT EXISTS created_by_username character varying;

-- ─── 3. Backfill : remplir le nom du support/admin pour les scans EXISTANTS ───
UPDATE public.scans s
SET created_by_username = a.discord_username
FROM public.admins a
WHERE s.created_by_discord_id IS NOT NULL
  AND s.created_by_username IS NULL
  AND a.discord_id = s.created_by_discord_id;

-- ─── 4. VÉRIFICATION : contrainte active ──────────────────────────────────
SELECT
  c.conname AS constraint_name,
  c.contype AS constraint_type,
  pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
WHERE c.conrelid = 'public.scans'::regclass
  AND c.contype IN ('u', 'p');

-- ─── 5. VÉRIFICATION : les 5 derniers scans (avec server_key + support) ───
SELECT scan_id, timestamp, hwid, server_key, pin_code,
       created_by_username, created_by_discord_id
FROM public.scans
ORDER BY timestamp DESC
LIMIT 5;