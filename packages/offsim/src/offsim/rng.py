"""Seeded randomness, one independent stream per thing.

Every random choice draws from a stream derived from the master seed plus
the identity of what is being generated -- ``("match", 700002, "optical")``.
So match 2 is the same whether or not match 1 was generated first, and
adding a scenario to one match does not shift the random numbers of another.
"""

from __future__ import annotations

import hashlib
import random
import uuid


def derive_seed(seed: int, *keys: object) -> int:
    """A 64-bit seed for ``keys`` under ``seed``, stable across runs and machines."""
    digest = hashlib.sha256(repr((seed, *keys)).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def rng_for(seed: int, *keys: object) -> random.Random:
    """An independent random stream for ``keys``."""
    return random.Random(derive_seed(seed, *keys))


def uuid_for(seed: int, *keys: object) -> uuid.UUID:
    """A deterministic version-4 UUID for ``keys``, for client-generated ids."""
    digest = hashlib.sha256(repr(("uuid", seed, *keys)).encode("utf-8")).digest()
    return uuid.UUID(bytes=digest[:16], version=4)
