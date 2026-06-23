"""Match free conversation text to a registered trigger phrase.

Ported from the reachy_manipulation reference (``manual_task/task_matcher.py``)
so chat/voice resolution has the same feel: matching is token/word aware (no raw
substring matching) so a short trigger like "hi" no longer fires inside an
unrelated word such as "which", stopwords are ignored so "push the box" cannot
match "which box is..." on "the"/"box" alone, and longer trigger phrases are
preferred because they are more specific. The best-scoring candidate above
``MATCH_THRESHOLD`` is returned deterministically.
"""

from __future__ import annotations

import re
import difflib
from dataclasses import dataclass


# Minimum confidence required to trigger an action from free text. Kept low
# enough to catch loosely-phrased requests ("do the omx moveit") while the model
# only calls the resolver when the user actually asks to control a robot.
MATCH_THRESHOLD = 0.5

# Filler words that must not, on their own, count as a phrase match.
_STOPWORDS = frozenset(
    {
        "a", "an", "the", "to", "on", "of", "in", "it", "is", "are", "this",
        "that", "your", "my", "please", "can", "could", "would", "you", "i",
        "and", "or", "with", "for", "do", "does", "at", "be", "me", "us", "one",
        "run", "start", "go", "let", "lets", "now",
    }
)


@dataclass(frozen=True)
class TriggerCandidate:
    """One resolvable target and the phrases that should fire it."""

    kind: str
    name: str
    phrases: list[str]


@dataclass(frozen=True)
class TriggerMatch:
    kind: str
    name: str
    matched_phrase: str
    score: float


def best_trigger_match(user_text: str, candidates: list[TriggerCandidate]) -> TriggerMatch | None:
    """Return the best candidate for ``user_text`` or None below the threshold.

    Candidates earlier in the list win on exact score ties (callers pass higher
    priority catalogs first), and within a candidate the longest matching phrase
    wins so more specific triggers are preferred.
    """
    text = _norm(user_text)
    if not text:
        return None
    text_tokens = text.split()
    text_token_set = set(text_tokens)

    best: TriggerMatch | None = None
    best_score = 0.0
    best_len = 0
    for candidate in candidates:
        cand_score = 0.0
        cand_len = 0
        cand_phrase = ""
        for phrase in candidate.phrases:
            normalized = _norm(str(phrase))
            if not normalized:
                continue
            score = _phrase_score(normalized, text, text_tokens, text_token_set)
            phrase_len = len(normalized.split())
            if score > cand_score or (score == cand_score and phrase_len > cand_len):
                cand_score = score
                cand_len = phrase_len
                cand_phrase = phrase
        if cand_score > best_score or (cand_score == best_score and cand_len > best_len):
            best_score = cand_score
            best_len = cand_len
            best = TriggerMatch(candidate.kind, candidate.name, cand_phrase, round(cand_score, 3))
    return best if best is not None and best_score >= MATCH_THRESHOLD else None


def _phrase_score(
    phrase: str,
    text: str,
    text_tokens: list[str],
    text_token_set: set[str],
) -> float:
    """Score how well ``phrase`` (a trigger phrase) matches the user text."""
    if phrase == text:
        return 1.0
    phrase_tokens = phrase.split()
    if _contains_tokens(text_tokens, phrase_tokens):
        # Whole-phrase match on word boundaries; longer phrases are more specific.
        if len(phrase_tokens) == 1:
            return 0.8
        return min(0.97, 0.85 + 0.03 * len(phrase_tokens))
    # Partial match: how much of the phrase's informative (non-stopword) words
    # are present, blended with overall string similarity.
    content = [token for token in phrase_tokens if token not in _STOPWORDS] or phrase_tokens
    coverage = sum(1 for token in content if token in text_token_set) / len(content)
    ratio = difflib.SequenceMatcher(None, phrase, text).ratio()
    if len(phrase_tokens) >= 2 and len(content) >= 2 and coverage >= 0.5:
        return min(0.86, 0.45 + 0.4 * coverage + 0.1 * ratio)
    # A single distinctive content word present (e.g. "moveit", "bringup") is a
    # decent signal on its own.
    if len(content) == 1 and content[0] in text_token_set and len(content[0]) >= 4:
        return 0.6
    if ratio >= 0.75:
        return min(0.7, ratio)
    return 0.0


def _contains_tokens(haystack: list[str], needle: list[str]) -> bool:
    """True if ``needle`` appears as a contiguous run of whole tokens in ``haystack``."""
    if not needle or len(needle) > len(haystack):
        return False
    first = needle[0]
    for start in range(len(haystack) - len(needle) + 1):
        if haystack[start] == first and haystack[start : start + len(needle)] == needle:
            return True
    return False


def _norm(text: str) -> str:
    lowered = text.strip().lower()
    lowered = lowered.replace("_", " ")
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()
