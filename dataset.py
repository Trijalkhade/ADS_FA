"""
dataset.py — Loads unigram_freq.csv, filters and ranks words,
then builds all data structures at import time.

Exports:
    trie              — Trie with top 10k words
    bktree            — BKTree with top 5k words  (faster search)
    word_freq         — dict word -> normalised frequency (0–10000)
    letter_frequency  — dict char -> normalised frequency (0.0–1.0)
    letter_edges      — list of {from, to, weight} for graph visualisation
"""

import csv
import os
import sys
import time
import pickle

from structures import Trie, BKTree

_HERE = os.path.dirname(__file__)
_CSV  = os.path.join(_HERE, 'unigram_freq.csv')
_CACHE = os.path.join(_HERE, 'cache.pkl')

if os.path.exists(_CACHE):
    print("[*] Loading data structures from cache.pkl ...", flush=True)
    t0 = time.time()
    with open(_CACHE, 'rb') as f:
        trie, bktree, word_freq, letter_frequency, letter_edges, bigram_freq = pickle.load(f)
    print(f"[*] Cache loaded in {time.time()-t0:.2f}s", flush=True)

else:
    # ─────────────────────────────────────────────────────────────────────────────
    #  1. Load & Filter Words
    # ─────────────────────────────────────────────────────────────────────────────
    print("[*] Loading words from unigram_freq.csv ...", flush=True)
    t0 = time.time()

    raw: list[tuple[str, int]] = []   # (word, raw_count) in frequency order
    MAX_WORDS = 100_000 

    with open(_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            word = row['word'].strip().lower()
            try:
                count = int(row['count'])
            except ValueError:
                continue

            # Keep only pure alphabetic words, length 3–18
            if word.isalpha() and 3 <= len(word) <= 18:
                raw.append((word, count))

            if len(raw) >= MAX_WORDS:
                break

    print(f"  {len(raw)} words loaded in {time.time()-t0:.2f}s", flush=True)


    # ─────────────────────────────────────────────────────────────────────────────
    #  2. Normalise Frequencies  (0–10000 scale, rank-based)
    # ─────────────────────────────────────────────────────────────────────────────
    #  Word at rank 0 gets freq 10000, rank 9999 gets freq 1.
    #  This keeps the Trie heap comparisons meaningful and the frontend bar widths
    #  easy to render as a percentage.

    word_freq: dict[str, int] = {}
    for rank, (word, _) in enumerate(raw):
        word_freq[word] = max(1, 10_000 - rank)


    # ─────────────────────────────────────────────────────────────────────────────
    #  3. Letter Frequencies  (for graph node sizes)
    # ─────────────────────────────────────────────────────────────────────────────
    print("[*] Computing letter statistics ...", flush=True)

    _letter_raw: dict[str, int] = {}
    for word, freq in word_freq.items():
        for ch in word:
            _letter_raw[ch] = _letter_raw.get(ch, 0) + freq

    _max_lf = max(_letter_raw.values()) if _letter_raw else 1
    letter_frequency: dict[str, float] = {
        ch: round(cnt / _max_lf, 6)
        for ch, cnt in _letter_raw.items()
    }


    # ─────────────────────────────────────────────────────────────────────────────
    #  4. Letter Bigram Co-occurrence  (for graph edges)
    # ─────────────────────────────────────────────────────────────────────────────
    _bigram_raw: dict[tuple[str, str], int] = {}
    for word, freq in word_freq.items():
        for i in range(len(word) - 1):
            pair = (word[i], word[i + 1])
            _bigram_raw[pair] = _bigram_raw.get(pair, 0) + freq

    _max_co = max(_bigram_raw.values()) if _bigram_raw else 1

    # Only keep edges above 1% of max co-occurrence (removes near-zero noise)
    letter_edges: list[dict] = [
        {'from': a, 'to': b, 'weight': round(cnt / _max_co, 6)}
        for (a, b), cnt in _bigram_raw.items()
        if cnt / _max_co > 0.01
    ]
    letter_edges.sort(key=lambda e: -e['weight'])

    # Fast lookup dict: (char_a, char_b) -> normalized weight
    bigram_freq: dict[tuple[str,str], float] = {
        (a, b): round(cnt / _max_co, 6)
        for (a, b), cnt in _bigram_raw.items()
    }

    print(f"  {len(letter_edges)} significant letter-pair edges", flush=True)


    # ─────────────────────────────────────────────────────────────────────────────
    #  5. Build Trie  (all 10k words)
    # ─────────────────────────────────────────────────────────────────────────────
    print("[*] Building Trie ...", flush=True)
    t1 = time.time()

    trie = Trie()
    for word, freq in word_freq.items():
        trie.insert(word, freq)

    print(f"  Trie: {trie.node_count} nodes, {trie.word_count} words "
          f"({time.time()-t1:.2f}s)", flush=True)
    trie.compute_subtree_counts()
    print("  Subtree counts computed.", flush=True)

    # ─────────────────────────────────────────────────────────────────────────────
    #  6. Build BKTree  (top 50k words — better coverage, still efficient)
    # ─────────────────────────────────────────────────────────────────────────────
    print("[*] Building BKTree ...", flush=True)
    t2 = time.time()

    bktree = BKTree()

    # CSV already sorted by frequency → no need to sort again
    bktree_words = list(word_freq.keys())[:50_000]

    for i, word in enumerate(bktree_words):
        bktree.insert(word)
        if (i + 1) % 5000 == 0:   # adjusted progress step for 50k
            print(f"  ... {i+1}/50000", flush=True)

    print(f"  BKTree: {bktree.size} nodes ({time.time()-t2:.2f}s)", flush=True)

    print("[*] Saving structures to cache.pkl ...", flush=True)
    with open(_CACHE, 'wb') as f:
        pickle.dump((trie, bktree, word_freq, letter_frequency, letter_edges, bigram_freq), f)

    print(f"[*] All structures ready & cached! Total startup: {time.time()-t0:.2f}s", flush=True)