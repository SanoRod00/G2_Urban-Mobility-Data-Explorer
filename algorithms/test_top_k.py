"""Run: python -m algorithms.test_top_k"""
import random
from algorithms.top_k import top_k

def test_all():
    assert top_k([5, 1, 9, 3, 7], 3) == [9, 7, 5]
    assert top_k([3, 1, 2], 10) == [3, 2, 1]
    assert top_k([], 3) == [] and top_k([1, 2], 0) == []        # empty, k = 0
    assert top_k([1, 2, 3, 4, 5, 6], 3) == [6, 5, 4]            # already sorted
    assert top_k([6, 5, 4, 3, 2, 1], 3) == [6, 5, 4]
    items = [("a", 5), ("b", 5), ("c", 9)] 
    assert top_k(items, 2, key=lambda x: x[1]) == [("c", 9), ("a", 5)]
    assert top_k([3, None, float("nan"), 9, 1], 3) == [9, 3, 1]  # None and NaN skipped
    try:
        top_k([1], -1)
        raise AssertionError("negative k should fail")
    except ValueError:
        pass
    rng = random.Random(1)
    for _ in range(200):
        data = [(rng.randint(0, 15), i) for i in range(rng.randint(0, 50))]
        k = rng.randint(0,20)
        assert top_k(data, k, key=lambda x: x[0]) == sorted(data, key=lambda x: (-x[0], x[1]))[:k]



if __name__ == "__main__":
    test_all()
    print("All tests passed")

    
    