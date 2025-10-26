import threading
import time
import random

def refresh_kbuckets(node, interval=3600):
    while True:
        for bucket_range in node.kbucket_ranges:
            random_id = random.randint(*bucket_range)
            node.find_node(random_id)
        time.sleep(interval)