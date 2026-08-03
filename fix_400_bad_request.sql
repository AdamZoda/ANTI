-- ═══════════════════════════════════════════════════════════════════════════
-- 🛡️ ANTI — FIX 400 BAD REQUEST : scan_id UNIQUE + colonnes manquantes
-- ═══════════════════════════════════════════════════════════════════════════
-- Le PostgREST "resolution=merge-duplicates" exige une contrainte UNIQUE
-- sur scan_id. Sans elle → HTTP 400 → le scan n'est jamais inséré.
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 1. Colonne created_by_username (l'EXE l'envoie maintenant) ──────────
ALTER TABLE public.scans ADD COLUMN IF NOT EXISTS created_by_username character varying;

-- ─── 2. Supprimer les doublons scan_id si existants (nettoyage pré-UNIQUE) ──
DELETE FROM public.scans s
USING public.scans s2
WHERE s.ctid < s2.ctid
  AND s.scan_id = s2.scan_id;

-- ─── 3. CRITIQUE : Contrainte UNIQUE sur scan_id ─────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.scans'::regclass
      AND contype IN ('u', 'p')
  ) THEN
    ALTER TABLE public.scans ADD CONSTRAINT scans_scan_id_unique UNIQUE (scan_id);
    RAISE NOTICE '✅ Contrainte UNIQUE ajoutée sur scan_id';
  ELSE
    RAISE NOTICE 'ℹ️  Contrainte UNIQUE/PRIMARY existe déjà sur scans';
  END IF;
END $$;

-- ─── 4. Backfill des noms depuis admins ──────────────────────────────────
UPDATE public.scans s
SET created_by_username = a.discord_username
FROM public.admins a
WHERE s.created_by_discord_id IS NOT NULL
  AND s.created_by_username IS NULL
  AND a.discord_id = s.created_by_discord_id;

-- ─── 5. VÉRIFICATION ────────────────────────────────────────────────────
SELECT c.conname, pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
WHERE c.conrelid = 'public.scans'::regclass AND c.contype IN ('u','p');

SELECT scan_id, timestamp, server_key, pin_code, created_by_username, created_by_discord_id
FROM public.scans ORDER BY timestamp DESC LIMIT 5;