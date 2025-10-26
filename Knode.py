import os
import hashlib
import msgpackrpc
from xor import xor_distance, select_bucket

class KademliaNode:
    def __init__(self, ip, port, node_id=None):
        self.ip = ip
        self.port = port
        self.node_id = node_id or hashlib.sha1(f"{ip}:{port}".encode()).hexdigest()
        self.kbucket = {}
        self.search_node = 2
        self.k = 1

    def ping(self): #return self contact information
        return {
            "ip": self.ip,
            "port": self.port,
            "node_id": self.node_id
        }

   
    def create(self): #creat network
        self.kbucket = {}


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
                closest_nodes = client.call("find_node", self.node_id)
                # closest_nodes 可能是一個 dict 或 list，統一處理成 list
                if isinstance(closest_nodes, dict):
                    closest_nodes = [closest_nodes]

                for node in closest_nodes:
                    node_ip = node.get("ip") or node.get(b"ip").decode()
                    node_port = node.get("port") or node.get(b"port")
                    node_id = node.get("node_id") or node.get(b"node_id").decode()

                    self.add_node({
                        "ip": node_ip,
                        "port": node_port,
                        "node_id": node_id
                    })

                    try:
                        other_client = msgpackrpc.Client(msgpackrpc.Address(node_ip, node_port))
                        other_client.call("add_node", {"ip": self.ip, "port": self.port, "node_id": self.node_id})
                    finally:
                        other_client.close()


            except Exception as e:
                print(f"Failed to get nodes from contact: {e}")
            
            client.call("add_node", {"ip": self.ip, "port": self.port, "node_id": self.node_id})
            print(self.kbucket)
        except Exception as e:
            print(f"Failed to connect to {contact_ip}:{contact_port}: {e}")
        finally:
            client.close()


    def find_node(self, key):
        print(f"[{self.port}] finding: {key[:6]}...")
        distance = xor_distance(self.node_id, key)
        target_bucket = distance.bit_length() - 1

        # 往上找有節點的 bucket
        while target_bucket >= 0 and (target_bucket not in self.kbucket or not self.kbucket[target_bucket]):
            target_bucket -= 1

        if target_bucket < 0:
            return {
                "ip": str(self.ip),
                "port": int(self.port),
                "node_id": str(self.node_id)
            }

        # 取 bucket 裡最近的節點
        clearest_node = self.kbucket[target_bucket][0]
        for node in self.kbucket[target_bucket]:
            if xor_distance(node["node_id"], key) < xor_distance(clearest_node["node_id"], key):
                clearest_node = node

        # 遞迴尋找
        clearest_result = None
        try:
            client = msgpackrpc.Client(msgpackrpc.Address(clearest_node["ip"], clearest_node["port"]))
            clearest_result = client.call("find_node", key)  # 不帶 timeout
        except Exception as e:
            print(f"[{self.port}] find_node RPC error with {clearest_node['ip']}:{clearest_node['port']} → {e}")
        finally:
            if 'client' in locals():
                client.close()
            
        self_dist = xor_distance(self.node_id, key)
        clearest_dist = xor_distance(clearest_node["node_id"], key)
        if isinstance(clearest_result, dict) and ("node_id" in clearest_result or b"node_id" in clearest_result):
            node_id_key = "node_id" if "node_id" in clearest_result else b"node_id"
            result_dist = xor_distance(clearest_result[node_id_key], key)
        else:
            result_dist = float('inf')
            if clearest_result is not None:
                print(f"⚠️ Invalid response from node {clearest_node['ip']}:{clearest_node['port']} → {clearest_result}")

        # 選擇最近的節點
        if self_dist <= clearest_dist and self_dist <= result_dist:
            return {
                "ip": str(self.ip),
                "port": int(self.port),
                "node_id": str(self.node_id)
            }
        elif clearest_dist <= result_dist:
            return clearest_node
        else:
            if isinstance(clearest_result, dict):
                self.add_node(clearest_result)
            return clearest_result




#還差add_node替換node應該要照簡報的保留活最久的、丟掉least-recently seen
        



    def kill(self): #kill the node
        os._exit(0)


    def add_node(self, node_info):
        # 統一資料型態
        node_info = {
            "ip": node_info.get("ip") or node_info.get(b"ip").decode(),
            "port": node_info.get("port") or node_info.get(b"port"),
            "node_id": node_info.get("node_id") or node_info.get(b"node_id").decode()
        }
        
        # 計算距離和對應 bucket
        distance = xor_distance(self.node_id, node_info["node_id"])
        bucket_index = select_bucket(distance)

        # 初始化 bucket
        if bucket_index not in self.kbucket:
            self.kbucket[bucket_index] = []

        existing_nodes = self.kbucket[bucket_index]

        # 檢查是否已存在
        for existing in existing_nodes:
            if existing["node_id"] == node_info["node_id"]:
                return  # 已存在，不加入

        # 總數限制 4
        total_nodes = sum(len(nodes) for nodes in self.kbucket.values())
        if total_nodes >= 4:
            # 嘗試替換死節點
            for idx, existing in enumerate(existing_nodes):
                client = msgpackrpc.Client(msgpackrpc.Address(existing["ip"], existing["port"]))
                try:
                    client.call("ping")
                except:
                    existing_nodes[idx] = node_info
                    self.kbucket[bucket_index] = existing_nodes
                    client.close()
                    return
                finally:
                    client.close()
            # 如果沒有死節點，替換最遠的
            farthest_idx = max(range(len(existing_nodes)), key=lambda i: xor_distance(existing_nodes[i]["node_id"], self.node_id))
            existing_nodes[farthest_idx] = node_info
            self.kbucket[bucket_index] = existing_nodes
            return

        # bucket 未滿 -> 加入新節點
        if len(existing_nodes) < 4:
            existing_nodes.append(node_info)
            self.kbucket[bucket_index] = existing_nodes




    def show_bucket(self):
        return self.kbucket