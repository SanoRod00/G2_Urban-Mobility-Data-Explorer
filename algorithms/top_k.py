"""Top-K with a hand-written min-heap. Time O(N log K), space O(K)."""


def _up(h, i):
    while i > 0 and h[i] < h[(i - 1) // 2]:
        p = (i - 1) // 2
        h[i], h[p] = h[p], h[i]
        i = p
def _down(h, i):
    while True:
        s = i
        for c in (2 * i + 1, 2 * i + 2):
            if c < len(h) and h[c] < h[s]:
                s = c
        if s == i:
            return
        h[i], h[s] = h[s], h[i]
        i = s
    
def top_k(items, k, key=None):
    """Return the k highest-scoring items, best first. Ties: first seen wins."""
    if k < 0:
        raise ValueError("k must b=nto be negative")
    heap = []
    for seq, item in enumerate(items):
        score = item if key is None else key(item)
        if score is None or score != score:     # skip None and NaN
            continue
        entry = (score, -seq, item)
        if len(heap) < k:
            heap.append(entry)
            _up(heap, len(heap) - 1)
        elif heap and entry > heap[0]:
            heap[0] = entry
            _down(heap, 0)
    out = []
    while heap:
        out.append(heap[0][2])
        heap[0] = heap[-1]
        heap.pop()
        if heap:
            _down(heap,0)
    return out[::-1]
