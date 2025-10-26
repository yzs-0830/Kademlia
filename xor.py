#functions for xor distance and bucket index
import math

MAX_BUCKETS= 4

def xor_distance(id1, id2):
    if isinstance(id1, str):
        id1 = int(id1, 16)
    elif isinstance(id1, bytes):
        id1 = int(id1.decode(), 16)
    
    if isinstance(id2, str):
        id2 = int(id2, 16)
    elif isinstance(id2, bytes):
        id2 = int(id2.decode(), 16)
    
    return id1 ^ id2


def select_bucket(distance):
    if distance == 0:
        return 0

    return distance.bit_length() - 1