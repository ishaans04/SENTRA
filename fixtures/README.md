# Fixtures

Deterministic, fictional material. No customer data, no real secrets, no live
endpoints, no copied production logs.

| Path | What it is |
| --- | --- |
| `manifests/default.yaml` | The support estate: zones, nodes, permitted relationships, invariants, and the controls an operator pre-authorised |
| `manifests/delivery.yaml` | A second estate, sharing no node names with the first |
| `scenarios/p0_scenario.jsonl` | 12 observations that compose a restricted-data-to-egress path (PS-001) |
| `scenarios/p1_scenario.jsonl` | 12 observations that compose a cross-actor execution channel (PS-002) |

A manifest is the declaration of what a population is *meant* to do. Nothing in
it is inferred from traffic, which is what makes a deviation meaningful rather
than merely unusual.

Scenarios are JSON Lines, one observation per line. Loading validates every line
through the same ingest boundary a real collector would cross, and rejects
repeated event ids or sequence numbers — both of which would make a replay
quietly stop matching its own description.
