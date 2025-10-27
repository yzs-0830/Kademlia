import os
import threading
import hashlib
import msgpackrpc
import time
from xor import xor_distance, select_bucket

class KademliaNode:
    def __init__(self, ip, port, node_id=None):
        self.ip = ip
        self.port = port
        self.node_id = node_id or hashlib.sha1(f"{ip}:{port}".encode()).hexdigest()
        self.kbucket = {}
        self.search_node = 2
        self.k = 1
        self.node_cache = []  # stack (LIFO)
        self.fail_count = {}  # node_id -> 連續失敗次數
        self.auto_ping_check = False

    def ping(self): #return self contact information
        return {
            "ip": str(self.ip),
            "port": int(self.port),
            "node_id": str(self.node_id)
        }

   
    def create(self): #creat network
        self.kbucket = {}

    def start_auto_ping(self, interval=2):
        """啟動背景自動 ping"""
        def ping_all_nodes():
            while True:
                time.sleep(interval)
                self.check_nodes()

        t = threading.Thread(target=ping_all_nodes, daemon=True)
        t.start()

    def check_nodes(self):
        """遍歷所有 bucket 的節點進行 ping 檢查"""
        for bucket_index, nodes in self.kbucket.items():
            for node in nodes[:]:  # 複製列表避免修改時出錯
                if node.get("inactive", False):
                    continue
                client = msgpackrpc.Client(msgpackrpc.Address(node["ip"], node["port"]), timeout=0.5)
                try:
                    client.call("ping")
                    self.fail_count[node["node_id"]] = 0
                except Exception as e:
                    self.fail_count[node["node_id"]] = self.fail_count.get(node["node_id"], 0) + 1
                    print(f"[{self.port}] Ping failed for {node['port']} ({self.fail_count[node['node_id']]}/5)")
                    if self.fail_count[node["node_id"]] >= 5:
                        self.replace_dead_node(node)
                finally:
                    client.close()


    def join(self, contact): 
        contact_ip = contact[b"ip"].decode()
        contact_port = contact[b"port"]
        contact_node_id = contact[b"node_id"].decode()
        client = msgpackrpc.Client(msgpackrpc.Address(contact_ip, contact_port)) 
        
        try: 
            pingcheck = client.call("ping") 
            print(f"Joined network via {contact_ip}:{contact_port}, got response: {pingcheck}")
            self.add_node({"ip": contact_ip, "port": contact_port, "node_id": contact_node_id})
            
            # 從 contact 取得更多節點
            try:
                closest_nodes = client.call("send_closest", self.node_id)
                # closest_nodes 可能是一個 dict 或 list，統一處理成 list
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
            except Exception as e:
                print(f"Failed to get nodes from contact: {e}")
            
            client.call("add_node", {"ip": self.ip, "port": self.port, "node_id": self.node_id})
            print(self.kbucket)
        except Exception as e:
            print(f"Failed to connect to {contact_ip}:{contact_port}: {e}")
        finally:
            client.close()

        self.start_auto_ping()
        self.auto_ping_check = True


    def find_node(self, key, max_steps=3):
        print("finding:", key)

        # 已知節點與已問過節點
        results = [{
            "ip": str(self.ip),
            "port": int(self.port),
            "node_id": str(self.node_id)
        }]
        visited = set()
        steps = 0

        def xor_key_distance(node):
            return xor_distance(node["node_id"], key)

        # 循環查找
        while steps < max_steps:
            # 找到最近且還沒問過的節點
            closest_node = None
            for node in sorted(results, key=xor_key_distance):
                if node["node_id"] not in visited:
                    closest_node = node
                    break

            if not closest_node:
                break

            visited.add(closest_node["node_id"])
            steps += 1

            # 呼叫 closest 的 send_closest（同節點直接用方法，不用 RPC）
            if closest_node["node_id"] == str(self.node_id):
                new_node = self.send_closest(key)
            else:
                # 這裡暫時假設跨節點還是用 RPC 或模擬返回
                # new_node = rpc_call(closest_node, "send_closest", key)
                continue  # 先簡化只用本節點測試

            if not new_node:
                break

            node_id_key = b"node_id" if b"node_id" in new_node else "node_id"
            ip_key = b"ip" if b"ip" in new_node else "ip"
            port_key = b"port" if b"port" in new_node else "port"

            closest_result = {
                "node_id": new_node[node_id_key].decode() if isinstance(new_node[node_id_key], bytes) else new_node[node_id_key],
                "ip": new_node[ip_key].decode() if isinstance(new_node[ip_key], bytes) else new_node[ip_key],
                "port": new_node[port_key]
            }

            # 如果 closest 已在 visited，停止迴圈
            if closest_result["node_id"] in visited:
                break

            results.append(closest_result)

        # 排序並返回距離 key 最近的節點
        results.sort(key=xor_key_distance)
        print(results)
        return results[0]




    def send_closest(self, key):
        distance = xor_distance(self.node_id, key)
        target_bucket = distance.bit_length() - 1

        # 往上找有節點的 bucket
        while target_bucket >= 0 and (target_bucket not in self.kbucket or not self.kbucket[target_bucket]):
            target_bucket -= 1

        if target_bucket < 0:
            # 沒有其他節點，就回傳自己
            return {
                "ip": str(self.ip),
                "port": int(self.port),
                "node_id": str(self.node_id)
            }

        # 找 bucket 中最接近 key 的節點
        closest = None
        for node in self.kbucket[target_bucket]:
            if node.get("inactive", False):
                continue
            if closest is None or xor_distance(node["node_id"], key) < xor_distance(closest["node_id"], key):
                closest = {
                "ip": str(node["ip"]),
                "port": int(node["port"]),
                "node_id": str(node["node_id"])
            }

        if closest is None:
            closest = {
                "ip": str(self.ip),
                "port": int(self.port),
                "node_id": str(self.node_id)
            }

        return closest


    def kill(self): #kill the node
        os._exit(0)


    def add_node(self, node_info):
        # 統一資料型態
        print("adding:", node_info)
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

        # 初始化 bucket
        if bucket_index not in self.kbucket:
            self.kbucket[bucket_index] = []

        existing_nodes = self.kbucket[bucket_index]

        # 檢查 node 是否已存在
        for existing in existing_nodes:
            if existing["node_id"] == node_info["node_id"]:
                existing["inactive"] = False
                return  # 已存在，不加入

        # 總數限制 4
        total_nodes = sum(len(nodes) for nodes in self.kbucket.values())
        if total_nodes >= 4:
            self.node_cache.append(node_info)
            return  # 放入cache，總數已滿

        # bucket 未滿 -> 加入新節點
        if len(existing_nodes) < 4:
            existing_nodes.append(node_info)
            self.kbucket[bucket_index] = existing_nodes


    
    
    def replace_dead_node(self, dead_node):
        for bucket_index, nodes in self.kbucket.items():
            for n in nodes:
                if n["node_id"] == dead_node["node_id"]:
                    if self.node_cache:
                        new_node = self.node_cache.pop()
                        print(f"[{self.port}] Replacing {dead_node['port']} with {new_node['port']} from cache")
                        nodes.remove(n)
                        nodes.append(new_node)
                        self.fail_count[new_node["node_id"]] = 0
                    else:
                        print(f"[{self.port}] No cached nodes, marking {dead_node['port']} inactive")
                        n["inactive"] = True
                    return




    def show_bucket(self):
        return self.kbucket