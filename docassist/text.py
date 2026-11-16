"""Small text helpers: splitting into sentences and words.

Search works on words, so "Deposits", "deposit" and "DEPOSIT" all need to
end up as the same word. That's what tokens() does.
"""

from __future__ import annotations

import re

# Very common words that don't help to find anything. The last line is question
# filler: "How much is..." shouldn't match every sentence with "much" in it.
STOP_WORDS = frozenset("""
a about above after again against all am an and any are as at be because been before being
below between both but by can could did do does doing down during each few for from further
had has have having he her here hers herself him himself his how i if in into is it its itself
just me more most my myself no nor not now of off on once only or other our ours ourselves out
over own same she should so some such than that the their theirs them themselves then there
these they this those through to too under until up very was we were what when where which
while who whom why will with would you your yours yourself yourselves
much many please tell
""".split())

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
# A sentence ends with . ! or ? followed by a space, or at a blank line.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n\s*\n")


def stem(word: str) -> str:
    """Cut common endings so 'payments' and 'payment' match.

    It's rough on purpose: 'ies' -> 'y', then 's' is dropped, but not from
    short words or words ending in 'ss' (like 'address').
    """
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokens(text: str, keep_stop_words: bool = False) -> list[str]:
    """Lower case words with their endings cut, ready for searching."""
    words = (w.replace("'", "") for w in _WORD.findall(text.lower()))
    return [stem(w) for w in words if keep_stop_words or w not in STOP_WORDS]


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Where each sentence starts and ends in the text, skipping blank space."""
    spans = []
    start = 0
    for match in _SENTENCE_END.finditer(text):
        spans.append((start, match.start()))
        start = match.end()
    spans.append((start, len(text)))
    return [(s, e) for s, e in (_trim(text, s, e) for s, e in spans) if s < e]


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def sentences(text: str) -> list[str]:
    """The text split into sentences."""
    return [" ".join(text[s:e].split()) for s, e in sentence_spans(text)]
