"""
Lightweight in-memory student session state.

This is intentionally NOT a database. It's a hackathon-appropriate in-process
store that lets /practice and /learn share context within one running server:
a misconception surfaced while a student answers practice questions can
inform the wording of their *next* /learn call for the same concept, closing
the loop between "adaptive questioning" and "personalized teaching" that the
spec calls for.

Tradeoff: state resets when the server restarts, and it is not shared across
multiple server processes/workers. That's an accepted limitation for an MVP;
swapping this module for a Redis- or DB-backed version later requires no
changes to callers, since they only use the functions below.
"""

from __future__ import annotations

import threading
from collections import defaultdict
from typing import Dict, List, Tuple

_lock = threading.Lock()

_StudentConceptKey = Tuple[str, str]

# (student_id, concept) -> most recent misconceptions observed via /practice,
# most-recent-last, capped at 5 entries.
_misconceptions: Dict[_StudentConceptKey, List[str]] = defaultdict(list)

# (student_id, concept) -> number of times /learn has been called for this pair.
_learn_attempts: Dict[_StudentConceptKey, int] = defaultdict(int)


def record_misconception(student_id: str, concept: str, misconception: str) -> None:
    """Called by /practice whenever a wrong answer surfaces a likely misconception."""
    if not misconception:
        return
    key = (student_id, concept)
    with _lock:
        bucket = _misconceptions[key]
        if misconception not in bucket:
            bucket.append(misconception)
        if len(bucket) > 5:
            del bucket[: len(bucket) - 5]


def get_recent_misconceptions(student_id: str, concept: str) -> List[str]:
    """Called by /learn to reinforce teaching around misconceptions seen during practice."""
    with _lock:
        return list(_misconceptions.get((student_id, concept), []))


def record_learn_attempt(student_id: str, concept: str) -> int:
    """Increments and returns the attempt count for this student+concept pair."""
    key = (student_id, concept)
    with _lock:
        _learn_attempts[key] += 1
        return _learn_attempts[key]


def get_learn_attempt_count(student_id: str, concept: str) -> int:
    with _lock:
        return _learn_attempts.get((student_id, concept), 0)


def reset_all() -> None:
    """Test/demo utility — clears all in-memory state. Not exposed via any API route."""
    with _lock:
        _misconceptions.clear()
        _learn_attempts.clear()
