"""Generate synthetic temporal graph fixtures for testing.

Creates:
    data/fixtures/entities.parquet   — ~30 synthetic entities
    data/fixtures/relations.parquet  — ~100 synthetic relations (2020-2024)
    data/fixtures/documents.parquet  — ~10 synthetic documents

Planted drift scenarios:
    - PERSON-010: Changes community between 2021 and 2022
    - ORG-015: Becomes a bridge node in 2023
    - VESSEL-003: Gains many new connections in 2022
    - Control entities: ~10 entities with stable structure throughout

Run: python scripts/generate_fixtures.py [--output-dir data/fixtures]
"""

from __future__ import annotations

import argparse
import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def generate_fixtures(output_dir: str = "data/fixtures", seed: int = 42) -> None:
    """Generate synthetic parquet fixture files.

    Args:
        output_dir: Directory to write fixture parquet files.
        seed: Random seed for reproducibility.
    """
    rng = np.random.RandomState(seed)
    os.makedirs(output_dir, exist_ok=True)
    out = Path(output_dir)

    # -----------------------------------------------------------------------
    # 1. Documents
    # -----------------------------------------------------------------------
    docs = []
    for i in range(1, 12):
        year = 2019 + (i % 5)
        docs.append({
            "doc_id": f"DOC-{i:03d}",
            "title": f"UN Panel of Experts Report {year} — Supplementary {i}",
            "report_date": date(year, 6, 15),
            "source": "UN Panel of Experts",
            "url": f"https://example.un.org/reports/dprk/{year}/doc{i:03d}",
        })
    docs_df = pd.DataFrame(docs)
    docs_df["report_date"] = pd.to_datetime(docs_df["report_date"])
    docs_df.to_parquet(out / "documents.parquet", index=False)
    print(f"✓ documents.parquet — {len(docs)} records")

    # -----------------------------------------------------------------------
    # 2. Entities
    # -----------------------------------------------------------------------
    entities = []

    # Organizations (ORG-001 to ORG-015)
    org_names = [
        "Korea Namgang Trading Corp",
        "Daedong Credit Bank",
        "Korea National Insurance Corp",
        "Ryonbong General Corp",
        "Green Pine Associated Corp",
        "Ocean Maritime Management",
        "Korea Kumryong Trading Corp",
        "Paeksol General Trading Corp",
        "Korea Ryonha Machinery Corp",
        "Tanchon Commercial Bank",
        "Korea Kwangson Banking Corp",
        "Korea Ryonbong General Corp",
        "Mansudae Overseas Projects",
        "Korea Kwangson Mining Corp",
        "Singwang Economics & Trading Corp",  # ORG-015: bridge node in 2023
    ]
    for i, name in enumerate(org_names, 1):
        entities.append({
            "entity_id": f"ORG-{i:03d}",
            "entity_label": name,
            "entity_type": "ORG",
            "first_seen": date(2019, 1, 1),
            "last_seen": date(2024, 12, 31),
        })

    # Persons (PERSON-001 to PERSON-010)
    person_names = [
        "Kim Tong-Chol",
        "Ri Tong-Il",
        "Kim Sok-Chol",
        "Pak Myong-Ho",
        "Jon Il-Chun",
        "Ri Jong-Won",
        "Kim Kwang-Yon",
        "Sin Myong-Ho",
        "Rim Kwang-Il",
        "Mun Chol-Myong",  # PERSON-010: community change in 2022
    ]
    for i, name in enumerate(person_names, 1):
        entities.append({
            "entity_id": f"PERSON-{i:03d}",
            "entity_label": name,
            "entity_type": "PERSON",
            "first_seen": date(2019, 1, 1),
            "last_seen": date(2024, 12, 31),
        })

    # Vessels (VESSEL-001 to VESSEL-003)
    vessel_names = [
        "WISE HONEST",
        "BULK CARRIER SK2",
        "SERENE WINDS",  # VESSEL-003: gains many connections in 2022
    ]
    for i, name in enumerate(vessel_names, 1):
        entities.append({
            "entity_id": f"VESSEL-{i:03d}",
            "entity_label": name,
            "entity_type": "VESSEL",
            "first_seen": date(2020, 1, 1),
            "last_seen": date(2024, 12, 31),
        })

    # Locations (LOCATION-001 to LOCATION-002)
    location_data = [
        ("LOCATION-001", "Nampo Port", date(2019, 1, 1)),
        ("LOCATION-002", "Rajin-Sonbong Economic Zone", date(2019, 1, 1)),
    ]
    for eid, label, first_seen in location_data:
        entities.append({
            "entity_id": eid,
            "entity_label": label,
            "entity_type": "LOCATION",
            "first_seen": first_seen,
            "last_seen": date(2024, 12, 31),
        })

    entities_df = pd.DataFrame(entities)
    entities_df["first_seen"] = pd.to_datetime(entities_df["first_seen"])
    entities_df["last_seen"] = pd.to_datetime(entities_df["last_seen"])
    entities_df.to_parquet(out / "entities.parquet", index=False)
    print(f"✓ entities.parquet — {len(entities)} records")

    # -----------------------------------------------------------------------
    # 3. Relations with planted drift scenarios
    # -----------------------------------------------------------------------
    all_entity_ids = [e["entity_id"] for e in entities]
    doc_ids = [d["doc_id"] for d in docs]

    relations = []
    edge_counter = 1

    def add_edge(src, tgt, rel_type, year, doc_idx=None, weight=1.0):
        nonlocal edge_counter
        import uuid
        d = date(year, 6, 15)
        doc_id = doc_ids[doc_idx % len(doc_ids)] if doc_idx is not None else rng.choice(doc_ids)
        relations.append({
            "edge_id": str(uuid.uuid4()),
            "source_entity_id": src,
            "target_entity_id": tgt,
            "relation_type": rel_type,
            "weight": weight,
            "source_doc_id": doc_id,
            "report_date": d,
        })
        edge_counter += 1

    # -------- Stable backbone (2020-2024) --------
    # Core ORG cluster A: ORG-001, ORG-002, ORG-003, ORG-004
    stable_cluster_a = ["ORG-001", "ORG-002", "ORG-003", "ORG-004"]
    for year in range(2020, 2025):
        for i in range(len(stable_cluster_a)):
            for j in range(i + 1, len(stable_cluster_a)):
                add_edge(stable_cluster_a[i], stable_cluster_a[j], "ASSOCIATED_WITH", year)

    # Core ORG cluster B: ORG-005, ORG-006, ORG-007
    stable_cluster_b = ["ORG-005", "ORG-006", "ORG-007"]
    for year in range(2020, 2025):
        for i in range(len(stable_cluster_b)):
            for j in range(i + 1, len(stable_cluster_b)):
                add_edge(stable_cluster_b[i], stable_cluster_b[j], "TRANSACTS_WITH", year)

    # Stable person-org links
    stable_person_links = [
        ("PERSON-001", "ORG-001"),
        ("PERSON-002", "ORG-002"),
        ("PERSON-003", "ORG-003"),
        ("PERSON-004", "ORG-004"),
        ("PERSON-005", "ORG-005"),
        ("PERSON-006", "ORG-006"),
    ]
    for year in range(2020, 2025):
        for person, org in stable_person_links:
            add_edge(person, org, "EMPLOYS", year)

    # Stable vessel-location links
    for year in range(2020, 2025):
        add_edge("VESSEL-001", "LOCATION-001", "DOCKS_AT", year)
        add_edge("VESSEL-002", "LOCATION-002", "DOCKS_AT", year)
        add_edge("VESSEL-001", "ORG-001", "OPERATED_BY", year)

    # -------- PLANTED DRIFT SCENARIO 1: PERSON-010 community change --------
    # 2020, 2021: PERSON-010 is in cluster A (connected to ORG-001, ORG-002, ORG-003)
    for year in [2020, 2021]:
        add_edge("PERSON-010", "ORG-001", "ASSOCIATED_WITH", year)
        add_edge("PERSON-010", "ORG-002", "TRANSACTS_WITH", year)
        add_edge("PERSON-010", "ORG-003", "ASSOCIATED_WITH", year)

    # 2022, 2023, 2024: PERSON-010 moves to cluster B (connected to ORG-005, ORG-006, ORG-007)
    for year in [2022, 2023, 2024]:
        add_edge("PERSON-010", "ORG-005", "ASSOCIATED_WITH", year)
        add_edge("PERSON-010", "ORG-006", "TRANSACTS_WITH", year)
        add_edge("PERSON-010", "ORG-007", "ASSOCIATED_WITH", year)

    # -------- PLANTED DRIFT SCENARIO 2: ORG-015 becomes bridge in 2023 --------
    # 2020, 2021, 2022: ORG-015 weakly connected to cluster A
    for year in [2020, 2021, 2022]:
        add_edge("ORG-015", "ORG-001", "ASSOCIATED_WITH", year)

    # 2023, 2024: ORG-015 becomes a bridge between cluster A and cluster B
    for year in [2023, 2024]:
        # Connect to all nodes in both clusters — becomes the bridge
        for org in stable_cluster_a:
            add_edge("ORG-015", org, "TRANSACTS_WITH", year, weight=2.0)
        for org in stable_cluster_b:
            add_edge("ORG-015", org, "ASSOCIATED_WITH", year, weight=2.0)
        add_edge("ORG-015", "PERSON-007", "EMPLOYS", year)
        add_edge("ORG-015", "PERSON-008", "EMPLOYS", year)

    # -------- PLANTED DRIFT SCENARIO 3: VESSEL-003 gains connections in 2022 --------
    # 2020, 2021: VESSEL-003 only docks at LOCATION-001
    for year in [2020, 2021]:
        add_edge("VESSEL-003", "LOCATION-001", "DOCKS_AT", year)

    # 2022, 2023, 2024: VESSEL-003 gains many new connections
    for year in [2022, 2023, 2024]:
        add_edge("VESSEL-003", "LOCATION-001", "DOCKS_AT", year)
        add_edge("VESSEL-003", "LOCATION-002", "DOCKS_AT", year)
        add_edge("VESSEL-003", "ORG-001", "OPERATED_BY", year)
        add_edge("VESSEL-003", "ORG-008", "TRANSACTS_WITH", year)
        add_edge("VESSEL-003", "ORG-009", "ASSOCIATED_WITH", year)
        add_edge("VESSEL-003", "PERSON-009", "ASSOCIATED_WITH", year)

    # -------- Additional ORG-008, ORG-009, ORG-010 filler edges --------
    for year in range(2020, 2025):
        add_edge("ORG-008", "ORG-009", "TRANSACTS_WITH", year)
        add_edge("ORG-009", "ORG-010", "ASSOCIATED_WITH", year)
        add_edge("ORG-010", "PERSON-007", "EMPLOYS", year)
        add_edge("ORG-008", "LOCATION-001", "OPERATES_IN", year)

    # -------- Control stable entities: PERSON-007, PERSON-008 remain in their cluster --------
    for year in range(2020, 2025):
        add_edge("PERSON-007", "ORG-008", "EMPLOYS", year)
        add_edge("PERSON-008", "ORG-009", "EMPLOYS", year)
        add_edge("PERSON-009", "ORG-010", "ASSOCIATED_WITH", year)

    # Add ORG-011, ORG-012, ORG-013, ORG-014 with stable links
    for year in range(2020, 2025):
        add_edge("ORG-011", "ORG-012", "ASSOCIATED_WITH", year)
        add_edge("ORG-012", "ORG-013", "TRANSACTS_WITH", year)
        add_edge("ORG-013", "ORG-014", "ASSOCIATED_WITH", year)
        add_edge("ORG-011", "PERSON-001", "EMPLOYS", year)

    relations_df = pd.DataFrame(relations)
    relations_df["report_date"] = pd.to_datetime(relations_df["report_date"])
    relations_df.to_parquet(out / "relations.parquet", index=False)
    print(f"✓ relations.parquet — {len(relations)} records")

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    years = sorted(relations_df["report_date"].dt.year.unique())
    print(f"\nFixture summary:")
    print(f"  Entities: {len(entities)} ({len([e for e in entities if e['entity_type']=='ORG'])} ORG, "
          f"{len([e for e in entities if e['entity_type']=='PERSON'])} PERSON, "
          f"{len([e for e in entities if e['entity_type']=='VESSEL'])} VESSEL, "
          f"{len([e for e in entities if e['entity_type']=='LOCATION'])} LOCATION)")
    print(f"  Relations: {len(relations)} across years {years}")
    print(f"  Documents: {len(docs)}")
    print(f"\nPlanted drift scenarios:")
    print(f"  PERSON-010: Community change between 2021 and 2022")
    print(f"  ORG-015: Becomes bridge node in 2023")
    print(f"  VESSEL-003: Gains many connections in 2022")
    print(f"  ~10 control entities: Stable throughout 2020-2024")
    print(f"\nOutput: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic test fixtures")
    parser.add_argument(
        "--output-dir",
        default="data/fixtures",
        help="Output directory for fixture parquet files",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    # Change to project root if running from scripts/
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    os.chdir(project_root)

    generate_fixtures(args.output_dir, args.seed)
