# Methodology

## Entity Resolution
The entity-resolution pipeline reads DPRK report text, extracts mentions, embeds mention windows, and suggests alias candidates for analyst review. In this repo, GLiNER is the default extractor. Scores guide review; they are not automatic merges.

## Network Drift
Network drift is role change across adjacent annual snapshots. The score combines:
- embedding change
- neighbor turnover
- centrality movement
- community reassignment

UMAP is for plotting only.

## Dashboard Guidance
The dashboard now ships methodology, glossary, reading guidance, and recommended actions in its JSON payloads so explanations travel with the released data.

## Attribution and lineage

This toolkit builds on the public sanctions-network framing, report lineage, and baseline entity-network conventions documented in [Black Knights and Dark Network](https://github.com/RANDCorporation/black-knights-and-dark-network/).

Reused and adapted elements:
- report manifest and public source-link workflow as the citation source-of-truth;
- entity and relation graph structure for sanctions analysis;
- workflow from text evidence to network links.

Transformations made in this repo:
- split into a public monorepo with separate packages and dashboard surface;
- added analyst guardrails, review interfaces, and guided interpretation content;
- added temporal slicing, drift scoring, and ranked alerts for role change.

## Network Drift Lineage
See [network-drift-lineage.md](network-drift-lineage.md) for:
- a formal definition of network drift;
- the five signals used in scoring;
- a reproducible chain from source report to ranked drift alerts;
- practical analyst interpretation guidance.

For repository-level credit and citation guidance, see [`CITATION.cff`](../CITATION.cff).
