import os
import threading
import hashlib
import msgpackrpc
import time
import random
from xor import xor_distance, select_bucket

class KademliaNode:
    def __init__(self, ip, port, node_id=None):
        self.ip = ip
        self.port = port
        self.node_id = node_id or hashlib.sha1(f"{ip}:{port}".encode()).hexdigest()
        self.kbucket = {}
        self.replacement_cache = {}
        self.search_node_per_round = 1 #search per round (exponential)
        self.search_round_max = 10 #maximum search round
        self.send_back_node = 3 #nodes per send_closet
        self.total_k = 4 #total size of kbucket
        self.k_value = 1 #size per bucket
        self.fail_count = {}  # fail count for kbucket
        self.auto_ping_check = False #True after started ping check
        self.remove_limit = 3 #timeout exceed this then remove
        self.check_interval = 2 #interval between background ping check
        self.join_buffer = 10 #buffer for join process before background check


    def ping(self): #return self contact information
        return {
            "ip": str(self.ip),
            "port": int(self.port),
            "node_id": str(self.node_id)
        }


   
    def create(self): #creat network
        self.kbucket = {}



    def start_auto_ping(self): #background ping check initiate
        def ping_all_nodes():
            time.sleep(self.join_buffer)
            while True:
                time.sleep(self.check_interval)
                self.check_nodes()

        t = threading.Thread(target=ping_all_nodes, daemon=True)
        t.start()



    def check_nodes(self): #background kbucket health check
        for bucket_index, nodes in self.kbucket.items():
            for node in nodes[:]:
                if node.get("inactive", False):
                    continue
                client = msgpackrpc.Client(msgpackrpc.Address(node["ip"], node["port"]), timeout=0.5)
                try:
                    client.call("ping")
                    self.fail_count[node["node_id"]] = 0
                except Exception as e:
                    self.fail_count[node["node_id"]] = self.fail_count.get(node["node_id"], 0) + 1
                    if self.fail_count[node["node_id"]] >= self.remove_limit:
                        self.replace_dead_node(node)
                        break
                finally:
                    client.close()

        active_count = sum(1 for bucket in self.kbucket.values() for n in bucket if not n.get("inactive", False))
        if active_count < (self.total_k/2 + 1):
            random_key = format(random.getrandbits(160), '040x')
            self.find_node(random_key)

        


    def join(self, contact): #join network
        contact_ip = contact[b"ip"].decode()
        contact_port = contact[b"port"]
        contact_node_id = contact[b"node_id"].decode()
        client = msgpackrpc.Client(msgpackrpc.Address(contact_ip, contact_port)) 
        
        try: 
            self.add_node({"ip": contact_ip, "port": contact_port, "node_id": contact_node_id})
            
            # get another contact by find(self)
            try:
                closest_nodes = self.join_find(self.node_id)
                if isinstance(closest_nodes, dict):
                    closest_nodes = [closest_nodes]

                for node in closest_nodes:
                    node_ip = node.get("ip") or node.get(b"ip").decode()
                    node_port = node.get("port") or node.get(b"port")
                    node_nodeid = node.get("node_id") or node.get(b"node_id").decode()

                    another_client = msgpackrpc.Client(msgpackrpc.Address(node_ip, node_port)) 
                    another_client.call("add_node", {"ip": self.ip, "port": self.port, "node_id": self.node_id})
                    another_client.close()
                    self.add_node({
                        "ip": node_ip,
                        "port": node_port,
                        "node_id": node_nodeid
                    })
            finally:
                client.call("add_node", {"ip": self.ip, "port": self.port, "node_id": self.node_id})
        finally:
            client.close()

        if not self.auto_ping_check:
            self.start_auto_ping()
            self.auto_ping_check = True



    def find_node(self, key):  # find key
        results = [{
            "ip": str(self.ip),
            "port": int(self.port),
            "node_id": str(self.node_id)
        }]
        visited = set()
        known_nodes = {str(self.node_id)}
        rounds = 0

        def xor_key_distance(node):
            return xor_distance(node["node_id"], key)

        while rounds < self.search_round_max:  # keep searching before limit
            rounds += 1
            to_query = []

            if rounds <= 3:
                per_round = self.search_node_per_round + 1
            else:
                per_round = self.search_node_per_round
            
            for node in sorted(results, key=xor_key_distance):
                if node["node_id"] not in visited:
                    to_query.append(node)
                    if len(to_query) >= per_round:
                        break

            if not to_query:
                break

            any_new = False

            # iterative search
            for closest_node in to_query:
                visited.add(closest_node["node_id"])

                new_nodes = []
                if closest_node["node_id"] == str(self.node_id):
                    new_nodes = self.send_closest(key)
                else:
                    try:
                        client = msgpackrpc.Client(
                            msgpackrpc.Address(closest_node["ip"], closest_node["port"]),
                            timeout=0.5
                        )
                        response = client.call("send_closest", key)
                        client.close()
                        if response:
                            new_nodes = [
                                {
                                    (k.decode() if isinstance(k, bytes) else k):
                                    (v.decode() if isinstance(v, bytes) else v)
                                    for k, v in node_dict.items()
                                }
                                for node_dict in response
                            ]
                    except Exception:
                        continue

                # adding result
                for new_node in new_nodes:
                    if not new_node:
                        continue
                    node_entry = {
                        "node_id": new_node["node_id"],
                        "ip": new_node["ip"],
                        "port": new_node["port"]
                    }
                    if node_entry["node_id"] not in known_nodes:
                        results.append(node_entry)
                        known_nodes.add(node_entry["node_id"])
                        any_new = True

            # no new -> end
            if not any_new:
                break

        # sort and find result
        if results:
            results.sort(key=xor_key_distance)
            closest = {
                "ip": results[0]["ip"],
                "port": results[0]["port"],
                "node_id": results[0]["node_id"]
            }
            if closest["node_id"] != self.node_id:
                self.add_node(closest)  # renew kbucket
            return closest

        return None



    def join_find(self, key):  # find self when join
            results = [n for bucket in self.kbucket.values() for n in bucket] #remove self for join
            visited = set()
            known_nodes = {str(self.node_id)}
            rounds = 0

            def xor_key_distance(node):
                return xor_distance(node["node_id"], key)

            while rounds < self.search_round_max:  # keep searching before limit
                rounds += 1
                to_query = []
                per_round = self.search_node_per_round + 1

                
                for node in sorted(results, key=xor_key_distance):
                    if node["node_id"] not in visited:
                        to_query.append(node)
                        if len(to_query) >= per_round:
                            break

                if not to_query:
                    break

                any_new = False 

                # iterative search
                for closest_node in to_query:
                    visited.add(closest_node["node_id"])

                    new_nodes = []
                    if closest_node["node_id"] == str(self.node_id):
                        new_nodes = self.send_closest(key)
                    else:
                        try:
                            client = msgpackrpc.Client(
                                msgpackrpc.Address(closest_node["ip"], closest_node["port"]),
                                timeout=0.5
                            )
                            response = client.call("send_closest", key)
                            client.close()
                            if response:
                                new_nodes = [
                                    {
                                        (k.decode() if isinstance(k, bytes) else k):
                                        (v.decode() if isinstance(v, bytes) else v)
                                        for k, v in node_dict.items()
                                    }
                                    for node_dict in response
                                ]
                        except Exception:
                            continue

                    # adding result
                    for new_node in new_nodes:
                        if not new_node:
                            continue
                        node_entry = {
                            "node_id": new_node["node_id"],
                            "ip": new_node["ip"],
                            "port": new_node["port"]
                        }
                        if node_entry["node_id"] not in known_nodes:
                            results.append(node_entry)
                            known_nodes.add(node_entry["node_id"])
                            any_new = True

                # no new -> end
                if not any_new:
                    break

            # sort and find result
            if results:
                results.sort(key=xor_key_distance)
                closest = results[:1]
                return closest

            return None



    def send_closest(self, key):
        all_nodes = [node for bucket in self.kbucket.values() for node in bucket]

        # filter inactive and self
        candidates = [n for n in all_nodes if not n.get("inactive", False) and n["node_id"] != self.node_id]

        if not candidates:
            return [{
                "ip": str(self.ip),
                "port": int(self.port),
                "node_id": str(self.node_id)
            }]

        # 按 XOR 距離排序，取前 search_node_per_round 個
        candidates.sort(key=lambda n: xor_distance(n["node_id"], key))
        result = [{
            "ip": str(n["ip"]),
            "port": int(n["port"]),
            "node_id": str(n["node_id"])
        } for n in candidates[:self.send_back_node]]

        return result




    def kill(self): #kill the node
        os._exit(0)



    def add_node(self, node_info): #add node to kbucket
        node_info = {
            "ip": node_info.get("ip") or node_info.get(b"ip").decode(),
            "port": node_info.get("port") or node_info.get(b"port"),
            "node_id": node_info.get("node_id") or node_info.get(b"node_id").decode(),
            "inactive": False
        }

        if node_info["node_id"] == self.node_id:
            return
    
        distance = xor_distance(self.node_id, node_info["node_id"])
        bucket_index = select_bucket(distance)

        # initialize bucket
        if bucket_index not in self.kbucket:
            self.kbucket[bucket_index] = []

        existing_nodes = self.kbucket[bucket_index]

        # check if node already exists
        for existing in existing_nodes:
            if existing["node_id"] == node_info["node_id"]:
                existing["inactive"] = False
                return

        total_nodes = sum(len(nodes) for nodes in self.kbucket.values())
        if total_nodes >= self.total_k or len(existing_nodes) >= self.k_value:
            #store in replacement_cache
            if bucket_index not in self.replacement_cache:
                self.replacement_cache[bucket_index] = []

            self.replacement_cache[bucket_index] = [n for n in self.replacement_cache[bucket_index] if n["node_id"] != node_info["node_id"]]
            self.replacement_cache[bucket_index].append(node_info)


            # check inactive
            inactive_nodes = [n for n in existing_nodes if n.get("inactive", False)]

            # if inactive exist -> replace
            for dead_node in inactive_nodes:
                self.replace_dead_node(dead_node)
            return

        # add into bucket
        if len(existing_nodes) < self.k_value:
            existing_nodes.append(node_info)
            self.kbucket[bucket_index] = existing_nodes


    
    def replace_dead_node(self, dead_node):  # replace dead node with cache or turn inactive
        for bucket_index, bucket in self.kbucket.items():
            for n in bucket:
                if n["node_id"] == dead_node["node_id"]:
                    # remove dead_node
                    bucket.remove(n)

                    replacement_added = False
                    cache_candidates = self.replacement_cache.get(bucket_index, [])
                    notalive_cache = []

                    # cache health check
                    for candidate in cache_candidates[:]:
                        try:
                            client = msgpackrpc.Client(
                                msgpackrpc.Address(candidate["ip"], candidate["port"]),
                                timeout=0.1
                            )
                            pong = client.call("ping")
                            client.close()
                        except Exception:
                            notalive_cache.append(candidate)

                    # remove inactive
                    self.replacement_cache[bucket_index] = [
                        n for n in cache_candidates if n not in notalive_cache
                    ]
                    cache_candidates = self.replacement_cache[bucket_index]

                    # replace with same bucket
                    for i in range(len(cache_candidates)-1, -1, -1):
                        candidate = cache_candidates[i]
                        candidate_bucket_index = select_bucket(xor_distance(self.node_id, candidate["node_id"]))
                        candidate_bucket = self.kbucket.get(candidate_bucket_index, [])

                        if len(candidate_bucket) < self.k_value:
                            candidate["inactive"] = False
                            candidate_bucket.append(candidate)
                            self.kbucket[candidate_bucket_index] = candidate_bucket
                            self.fail_count[candidate["node_id"]] = 0
                            cache_candidates.pop(i)
                            replacement_added = True
                            break

                    # fallback: cross-bucket replacement
                    if not replacement_added:
                        for other_bucket_index, other_cache in self.replacement_cache.items():
                            if other_bucket_index == bucket_index:
                                continue

                            other_candidates = [
                                n for n in other_cache if n not in bucket and not n.get("inactive", False)
                            ]
                            for i in range(len(other_candidates)-1, -1, -1):
                                candidate = other_candidates[i]
                                candidate_bucket = self.kbucket.get(bucket_index, [])

                                if len(candidate_bucket) < self.k_value:
                                    candidate["inactive"] = False
                                    candidate_bucket.append(candidate)
                                    self.kbucket[bucket_index] = candidate_bucket
                                    self.fail_count[candidate["node_id"]] = 0
                                    self.replacement_cache[other_bucket_index].remove(candidate)
                                    replacement_added = True
                                    break
                            if replacement_added:
                                break

                    # keep dead_node inactive if no replacement
                    if not replacement_added:
                        dead_node["inactive"] = True
                        bucket.append(dead_node)

                    return
                