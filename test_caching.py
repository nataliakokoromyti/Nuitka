"""Small module for C code cache benchmarks."""

import math


def compute(n):
    total = 0.0
    for i in range(1, n + 1):
        total += math.sqrt(i)
    return total


def main():
    value = compute(1000)
    print("result", int(value))


if __name__ == "__main__":
    main()
