# The 24h learning loop

1. Every day run `snapshot_postiz.py` (read-only). It appends one row per published post to `snapshots.jsonl`:
   `{"ts","post_id","age_h","clip","hook","platform","slot_local","slot_hour","views","reach","likes","comments","shares","saves"}`.
2. Run `learn_report.py snapshots.jsonl`. It writes `leaderboard.md` (latest numbers per post plus the snapshot closest to 24h age, so clips of different ages compare fairly) and `LEARNINGS_DRAFT.md` (top and bottom clips, short versus long, slot-hour medians only where there are 3 or more posts).
3. Write the human-readable entry: what won, one hypothesis per pattern, the single change to test in the next batch. Date and timestamp every entry.
4. Confidence stays LOW until at least 15 posts per platform have a 24h reading, and it is lower while series differ (an older talk against a newer one is not a fair fight). Say so in the entry.
5. Compare like with like: same weekday, adjacent slots, one variable at a time. Length, hook type and slot are confounded in a first batch.
6. Never claim a view count you did not read from a snapshot. Quote the snapshot timestamp next to every number.
