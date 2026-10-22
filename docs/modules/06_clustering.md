# Module 6 — Nightly Unsupervised Clustering & Admin Analytics

> **Location**: `src/clustering/`
> **Schedule**: Nightly at 02:00 via APScheduler
> **Purpose**: Identify recurring unresolved query themes and surface them to administrators for canonical answer publishing

---

## Responsibility

This module is for **administrative analytics only**. It does not answer student questions. It identifies patterns in what students could not get answered so administrators can proactively publish information.

The "Top 5 Trends" dashboard shows administrators:
- What recurring questions are going unanswered
- How many students are affected
- Sample queries from each cluster
- A button to publish a canonical answer (which flows through Module 5 as a new FAQ)

---

## What Gets Clustered

Only **fallback queries** are clustered:

```sql
SELECT query_text, query_embedding
FROM analytics.query_logs
WHERE resolution IN ('fallback', 'escalated')   -- Not successfully deflected
  AND created_at > NOW() - INTERVAL '24 hours'
  AND included_in_cluster = FALSE
  AND query_embedding IS NOT NULL
```

**Excluded**:
- Successfully deflected queries (already answered)
- Directory queries (already answered by SQL)
- Queries with fewer than 10 tokens (likely noise)

---

## DBSCAN Clustering

### Why DBSCAN?

- Does not require specifying the number of clusters in advance
- Identifies noise/outlier queries (DBSCAN label = -1) and excludes them from trends
- Works with cosine distance on embedding vectors

### Parameters (Initial — Must Be Tuned)

```yaml
# config/clustering_config.yaml
clustering:
  algorithm: "dbscan"
  eps: 0.25           # Maximum distance between samples in a cluster
  min_samples: 3      # Minimum cluster size (< 3 → noise)
  metric: "cosine"
  min_cluster_size_to_report: 5   # Only surface clusters with ≥ 5 queries
  top_trends_count: 5
  fallback_algorithm: "hdbscan"   # If DBSCAN produces 0 valid clusters
```

**Tuning guidance**: After the first month of real query data, plot the k-distance graph (k = min_samples) to select a better `eps` value. Adjust `min_samples` based on typical daily query volume.

### HDBSCAN Fallback

If DBSCAN produces zero clusters with label ≥ 0 (all queries classified as noise), run HDBSCAN:

```python
import hdbscan
clusterer = hdbscan.HDBSCAN(
    min_cluster_size=3,
    metric='euclidean',   # HDBSCAN works better with euclidean on normalized vectors
    cluster_selection_method='eom'
)
```

---

## Pipeline

```python
async def run_nightly_clustering():
    # 1. Fetch unprocessed fallback queries from last 24h
    queries = await fetch_fallback_queries(hours=24)
    
    if len(queries) < 10:
        logger.info("Too few queries for meaningful clustering (< 10). Skipping.")
        return
    
    # 2. Extract embeddings
    embeddings = np.array([q.query_embedding for q in queries])
    
    # 3. Run DBSCAN
    from sklearn.cluster import DBSCAN
    labels = DBSCAN(eps=EPS, min_samples=MIN_SAMPLES, metric='cosine').fit_predict(embeddings)
    
    # 4. Fallback to HDBSCAN if needed
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    if n_clusters == 0:
        labels = run_hdbscan(embeddings)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    
    if n_clusters == 0:
        logger.info("No clusters found after both algorithms. Skipping trend update.")
        return
    
    # 5. For each valid cluster (label ≥ 0):
    results = []
    for label in set(labels):
        if label == -1:
            continue
        
        cluster_indices = np.where(labels == label)[0]
        cluster_queries = [queries[i] for i in cluster_indices]
        
        if len(cluster_queries) < MIN_CLUSTER_SIZE_TO_REPORT:
            continue
        
        # Extract representative queries (nearest to cluster centroid)
        centroid = embeddings[cluster_indices].mean(axis=0)
        distances = cosine_distances(embeddings[cluster_indices], [centroid]).flatten()
        rep_indices = distances.argsort()[:3]
        representative_queries = [cluster_queries[i].query_text for i in rep_indices]
        
        # Extract top keywords (TF-IDF on cluster query texts)
        top_keywords = extract_tfidf_keywords(
            [q.query_text for q in cluster_queries], top_n=5
        )
        
        results.append(ClusterResult(
            cluster_label=label,
            cluster_size=len(cluster_queries),
            top_keywords=top_keywords,
            representative_queries=representative_queries,
            query_ids=[q.id for q in cluster_queries]
        ))
    
    # 6. Sort by cluster size, take top 5
    results.sort(key=lambda r: r.cluster_size, reverse=True)
    top_5 = results[:5]
    
    # 7. Persist to analytics.cluster_results and analytics.top_trends
    today = date.today()
    for rank, result in enumerate(top_5, start=1):
        cluster_id = await db.insert_cluster_result(result, run_date=today)
        await db.upsert_top_trend(trend_date=today, rank=rank, cluster_id=cluster_id)
        
        # Mark queries as included in cluster
        await db.mark_queries_clustered(result.query_ids, cluster_id)
    
    logger.info(f"Clustering complete: {n_clusters} clusters, top {len(top_5)} surfaced")
```

---

## Admin Action: Publish Canonical Answer

When an admin sees a top-trend cluster and writes a canonical answer:

```python
async def publish_canonical_answer(
    cluster_id: str,
    canonical_answer: str,
    published_by: str
):
    # 1. Update cluster record
    db.update_cluster(cluster_id, 
                     canonical_answer=canonical_answer,
                     canonical_published_at=datetime.utcnow(),
                     canonical_published_by=published_by)
    
    # 2. Create a new FAQ document and send through Module 5 intake
    await ttl_manager.intake_document(
        content=canonical_answer,
        filename=f"faq_cluster_{cluster_id[:8]}.txt",
        source_url=f"admin_canonical/{cluster_id}",
        category="faqs",
        title=f"FAQ: {' '.join(cluster.top_keywords[:3])}",
        valid_from=date.today(),
        valid_until=None   # No expiry unless admin sets one
    )
    
    # 3. Admin still needs to approve in the review queue (same pipeline)
```

**This is not automatic**. The admin writes the answer, it goes into `pending_review`, and must be explicitly approved before entering the RAG index. This preserves human authority over what becomes an official answer.

---

## Tests (`tests/unit/test_clustering.py`)

| Test | Scenario | Expected |
|---|---|---|
| `test_minimum_query_threshold` | 9 queries available | Clustering skipped |
| `test_noise_excluded_from_trends` | Only 2 similar queries | Cluster size < min_samples; treated as noise |
| `test_top_5_limit` | 8 valid clusters | Only top 5 by size reported |
| `test_representative_queries_selected` | Valid cluster | 3 queries nearest to centroid returned |
| `test_hdbscan_fallback` | DBSCAN produces 0 clusters | HDBSCAN runs automatically |
| `test_queries_marked_processed` | Clustering runs | query_logs.included_in_cluster = TRUE |
| `test_canonical_answer_requires_approval` | Admin publishes answer | Enters pending_review, not directly active |
| `test_cluster_label_minus_one_excluded` | Noise points | Not included in any ClusterResult |
