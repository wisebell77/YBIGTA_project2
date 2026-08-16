-- Cluster-robust SE for the mean pair-level effect (intercept-only model).
-- Replace `pair_effects` with a table/CTE containing household_key, metric, diff.
WITH metric_means AS (
  SELECT metric, AVG(diff) AS mean_diff, COUNT(*) AS n,
    COUNT(DISTINCT household_key) AS clusters
  FROM pair_effects GROUP BY 1
),
cluster_scores AS (
  SELECT p.metric, p.household_key, SUM(p.diff - m.mean_diff) AS score,
    ANY_VALUE(m.mean_diff) AS mean_diff, ANY_VALUE(m.n) AS n,
    ANY_VALUE(m.clusters) AS clusters
  FROM pair_effects p JOIN metric_means m USING (metric)
  GROUP BY 1, 2
)
SELECT metric, ANY_VALUE(mean_diff) AS mean_diff,
  SQRT(ANY_VALUE(clusters) / (ANY_VALUE(clusters) - 1)
    * SUM(score * score) / (ANY_VALUE(n) * ANY_VALUE(n))) AS cluster_se,
  SAFE_DIVIDE(ANY_VALUE(mean_diff),
    SQRT(ANY_VALUE(clusters) / (ANY_VALUE(clusters) - 1)
      * SUM(score * score) / (ANY_VALUE(n) * ANY_VALUE(n)))) AS t_stat
FROM cluster_scores GROUP BY metric ORDER BY metric;
