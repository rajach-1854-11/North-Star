"""Simple sparse hashing using hashed token buckets."""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import List

TOKEN_RE = re.compile(r"[A-Za-z0-9_#.\-]+")


def _hash(token: str, dim: int = 2**20) -> int:
    """Hash a token into the sparse feature space."""

    digest = hashlib.md5(token.encode("utf-8"), usedforsecurity=False).hexdigest()
    return int(digest, 16) % dim


@dataclass
class SparseEncoded:
    """Sparse encoding result suitable for Qdrant sparse vectors."""

    indices: List[int]
    values: List[float]


def encode_sparse(text: str) -> SparseEncoded:
    """Tokenise *text* and return hashed sparse features."""

    tokens = [token.lower() for token in TOKEN_RE.findall(text)]
    counts = Counter(tokens)
    indices: List[int] = []
    values: List[float] = []
    for token, term_freq in counts.items():
        index = _hash(token)
        weight = math.log(1 + term_freq)
        indices.append(index)
        values.append(weight)
    return SparseEncoded(indices=indices, values=values)
