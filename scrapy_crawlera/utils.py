import math
import random


def exp_backoff(attempt, cap, base):
    """ Exponential backoff time """
    # this is a numerically stable version of
    # min(cap, base * 2 ** attempt)
    max_attempts = math.log(cap / base, 2)
    if attempt <= max_attempts:
        return base * 2 ** attempt
    return cap


def exp_backoff_full_jitter(attempt, cap, base):
    """ Exponential backoff time with Full Jitter """
    return random.uniform(0, exp_backoff(attempt, cap, base))
