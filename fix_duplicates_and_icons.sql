-- ═══════════════════════════════════════════════════════════════════════════
-- 🛡️ ANTI — NETTOYAGE SERVEURS DOUBLONS + AJOUT COLONNE ICON
-- ═══════════════════════════════════════════════════════════════════════════

-- 1. Ajouter colonne icon
ALTER TABLE public.servers ADD COLUMN IF NOT EXISTS icon text;

-- 2. Voir les doublons
SELECT name, COUNT(*) as count, ARRAY_AGG(server_key ORDER BY created_at) as keys
FROM public.servers GROUP BY name HAVING COUNT(*) > 1 ORDER BY count DESC;

-- 3. Supprimer les serveurs manuels aux clés non-standard quand un srv_dc_* existe
-- Ex: 'global' quand 'srv_dc_global' existe déjà
DELETE FROM public.servers s1
USING public.servers s2
WHERE s1.name = s2.name
  AND s1.server_key != s2.server_key
  AND s1.server_key NOT LIKE 'srv_dc_%'
  AND s2.server_key LIKE 'srv_dc_%';

-- 4. Pour les serveurs créés manuellement SANS version srv_dc_, garder le plus récent
DELETE FROM public.servers s
USING public.servers s2
WHERE s.name = s2.name
  AND s.id < s2.id
  AND s.server_key NOT LIKE 'srv_dc_%'
  AND s2.server_key NOT LIKE 'srv_dc_%';

-- 5. Vérification finale
SELECT server_key, name, icon, status, created_at
FROM public.servers ORDER BY name, created_at DESC;
