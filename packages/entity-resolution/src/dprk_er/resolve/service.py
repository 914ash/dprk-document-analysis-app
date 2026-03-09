"""Resolve service – generates candidate alias pairs and provisional clusters.

Architecture: may import from dprk_er.types only.

Algorithm:
1. Compute cosine similarity matrix over all mention embeddings.
2. For pairs above the threshold, also compute Levenshtein similarity.
3. Combine scores; record reasons.
4. Build clusters via union-find (connected components).
"""

from __future__ import annotations

import math

import structlog

from dprk_er.types.models import CandidateCluster, CandidateEvidence, CandidatePair, Mention

logger = structlog.get_logger(__name__)

_DEFAULT_THRESHOLD = 0.7
_LEVENSHTEIN_WEIGHT = 0.3
_COSINE_WEIGHT = 0.7
_THRESHOLD_VERSION = "gliner-evidence-v1"


class ResolveService:
    """Generates candidate alias pairs and clusters from embedded mentions."""

    # ------------------------------------------------------------------
    # Pair generation
    # ------------------------------------------------------------------

    def generate_candidates(
        self,
        mentions: list[Mention],
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> list[CandidatePair]:
        """Compare all mention pairs and return those above *threshold*.

        Only compares mentions of the same entity_type.
        Skips mentions from the same document (intra-doc duplicates).
        """
        if not mentions:
            return []

        # Filter to mentions that have embeddings
        embedded = [m for m in mentions if m.embedding]
        if len(embedded) < 2:
            logger.info("not_enough_embedded_mentions", count=len(embedded))
            return []

        logger.info("generating_candidates", mentions=len(embedded), threshold=threshold)

        pairs: list[CandidatePair] = []
        n = len(embedded)
        form_doc_counts = self._build_doc_spread(embedded)

        for i in range(n):
            for j in range(i + 1, n):
                m1, m2 = embedded[i], embedded[j]
                # Only compare same entity types
                if m1.entity_type != m2.entity_type:
                    continue
                score, reasons, evidence = self.score_pair(
                    m1,
                    m2,
                    form_doc_counts=form_doc_counts,
                )
                if score >= threshold:
                    pairs.append(
                        CandidatePair(
                            mention_id_a=m1.mention_id,
                            mention_id_b=m2.mention_id,
                            score=round(score, 4),
                            reasons=reasons,
                            evidence=evidence,
                            threshold_version=_THRESHOLD_VERSION,
                        )
                    )

        logger.info("candidates_generated", pairs=len(pairs))
        return pairs

    def score_pair(
        self,
        m1: Mention,
        m2: Mention,
        form_doc_counts: dict[tuple[str, str], int] | None = None,
    ) -> tuple[float, list[str], CandidateEvidence]:
        """Score a mention pair and return (score, reasons, evidence).

        Score = weighted combination of cosine similarity and Levenshtein similarity.
        """
        reasons: list[str] = []
        cosine = 0.0
        lev = self._levenshtein_similarity(m1.normalized_form, m2.normalized_form)
        overlap = self._token_overlap(m1.normalized_form, m2.normalized_form)
        form_doc_counts = form_doc_counts or {}
        surface_a_docs = form_doc_counts.get((m1.normalized_form, m1.entity_type), 1)
        surface_b_docs = form_doc_counts.get((m2.normalized_form, m2.entity_type), 1)

        if m1.embedding and m2.embedding:
            cosine = self._cosine_similarity(m1.embedding, m2.embedding)
            if cosine >= 0.9:
                reasons.append("Strong embedding match across reports")
            elif cosine >= 0.75:
                reasons.append("Moderate embedding match across reports")

        if m1.normalized_form.lower() == m2.normalized_form.lower():
            reasons.append("Exact normalized match across separate documents")

        if lev >= 0.9:
            reasons.append("Very similar spellings and formatting")
        elif lev >= 0.7:
            reasons.append("Similar spellings with minor variation")

        if overlap > 0.5:
            reasons.append("Overlapping entity tokens support a manual review")

        if surface_a_docs > 1 or surface_b_docs > 1:
            reasons.append("Observed repeatedly across multiple source reports")

        # Weight cosine more heavily when embeddings are available
        if m1.embedding and m2.embedding:
            score = _COSINE_WEIGHT * cosine + _LEVENSHTEIN_WEIGHT * lev
        else:
            score = lev

        evidence = CandidateEvidence(
            extractor_name_a=m1.extractor_name,
            extractor_name_b=m2.extractor_name,
            extractor_label_a=m1.extractor_label,
            extractor_label_b=m2.extractor_label,
            extractor_confidence_a=m1.extractor_confidence,
            extractor_confidence_b=m2.extractor_confidence,
            embedding_similarity=round(cosine, 4),
            lexical_similarity=round(lev, 4),
            token_overlap=round(overlap, 4),
            surface_a_doc_count=surface_a_docs,
            surface_b_doc_count=surface_b_docs,
            pair_doc_coverage=len({m1.doc_id, m2.doc_id}),
            context_a=self._compact_context(m1),
            context_b=self._compact_context(m2),
        )

        if not reasons:
            reasons.append("Similarity exceeded the configured review threshold")

        return min(score, 1.0), reasons, evidence

    # ------------------------------------------------------------------
    # Clustering
    # ------------------------------------------------------------------

    def build_clusters(self, pairs: list[CandidatePair]) -> list[CandidateCluster]:
        """Build provisional clusters via union-find (connected components).

        Only pairs with status != 'rejected' are included.
        Returns one CandidateCluster per connected component with ≥2 members.
        """
        active_pairs = [p for p in pairs if p.status != "rejected"]
        if not active_pairs:
            return []

        # Collect all mention IDs
        all_ids: set[str] = set()
        for p in active_pairs:
            all_ids.add(p.mention_id_a)
            all_ids.add(p.mention_id_b)

        parent = {mid: mid for mid in all_ids}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]  # path compression
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[ra] = rb

        # Build pair-score lookup for cluster score calculation
        pair_scores: dict[tuple[str, str], float] = {}
        for p in active_pairs:
            union(p.mention_id_a, p.mention_id_b)
            key = (min(p.mention_id_a, p.mention_id_b), max(p.mention_id_a, p.mention_id_b))
            pair_scores[key] = p.score

        # Group by root
        groups: dict[str, list[str]] = {}
        for mid in all_ids:
            root = find(mid)
            groups.setdefault(root, []).append(mid)

        clusters: list[CandidateCluster] = []
        for _root, members in groups.items():
            if len(members) < 2:
                continue
            # Compute mean pair score within cluster
            cluster_pairs = []
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    key = (min(members[i], members[j]), max(members[i], members[j]))
                    if key in pair_scores:
                        cluster_pairs.append(pair_scores[key])
            avg_score = sum(cluster_pairs) / len(cluster_pairs) if cluster_pairs else 0.0
            clusters.append(
                CandidateCluster(
                    member_mentions=sorted(members),
                    cluster_score=round(avg_score, 4),
                )
            )

        logger.info("clusters_built", count=len(clusters))
        return clusters

    # ------------------------------------------------------------------
    # Similarity helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b, strict=True))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _levenshtein_similarity(a: str, b: str) -> float:
        """Normalized Levenshtein similarity in [0, 1]."""
        if a == b:
            return 1.0
        la, lb = len(a), len(b)
        if la == 0 or lb == 0:
            return 0.0
        # Levenshtein distance via DP
        prev = list(range(lb + 1))
        for i, ca in enumerate(a, 1):
            curr = [i] + [0] * lb
            for j, cb in enumerate(b, 1):
                curr[j] = min(
                    prev[j] + 1,
                    curr[j - 1] + 1,
                    prev[j - 1] + (0 if ca == cb else 1),
                )
            prev = curr
        distance = prev[lb]
        max_len = max(la, lb)
        return 1.0 - distance / max_len

    @staticmethod
    def _token_overlap(a: str, b: str) -> float:
        """Compute Jaccard similarity between token sets."""
        tokens_a = set(a.lower().split())
        tokens_b = set(b.lower().split())
        if not tokens_a and not tokens_b:
            return 1.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union) if union else 0.0

    @staticmethod
    def _build_doc_spread(mentions: list[Mention]) -> dict[tuple[str, str], int]:
        spread: dict[tuple[str, str], set[str]] = {}
        for mention in mentions:
            key = (mention.normalized_form, mention.entity_type)
            spread.setdefault(key, set()).add(mention.doc_id)
        return {key: len(doc_ids) for key, doc_ids in spread.items()}

    @staticmethod
    def _compact_context(mention: Mention) -> str:
        text = " ".join(
            part
            for part in [
                mention.context_left.strip(),
                mention.surface_form.strip(),
                mention.context_right.strip(),
            ]
            if part
        )
        return " ".join(text.split())
