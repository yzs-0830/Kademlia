import msgpackrpc
import time

def new_client(ip, port):
    return msgpackrpc.Client(msgpackrpc.Address(ip, port))

# 節點列表
ip = "127.0.0.1"
ports = list(range(20001, 20017))  # 20001 ~ 20016
clients = [new_client(ip, p) for p in ports]

# 讓 20001 建立網路
clients[0].call("create")
print(f"Network created on {ports[0]}")
time.sleep(1)

# 節點加入（簡單樹狀加入）
join_plan = [
    (1, 0), (2, 1), (3, 0), (4, 0),
    (5, 4), (6, 0), (7, 4), (8, 0),
    (9, 0), (10, 5), (11, 0), (12, 6),
    (13, 0), (14, 7), (15, 0)
]

for node_idx, via_idx in join_plan:
    clients[node_idx].call("join", clients[via_idx].call("ping"))
    print(f"Node {ports[node_idx]} joined via {ports[via_idx]}")
    time.sleep(0.5)

# 先抓每個 node_id，存起來避免型態問題
node_ids = []

for c, p in zip(clients, ports):
    try:
        ping_result = c.call("ping")

        # 把 key decode 成 str
        ping_result_strkey = {k.decode() if isinstance(k, bytes) else k:
                              v for k, v in ping_result.items()}

        # 取 node_id
        nid = ping_result_strkey.get("node_id")
        if isinstance(nid, bytes):
            nid = nid.hex()
        node_ids.append(nid)

    except Exception as e:
        print(f"ping error → {e}")
        node_ids.append(None)



# 定義 find_plan: (查找者 idx, 目標節點 idx)
find_plan = [
    (0, 2), (0, 5), (0, 15),
    (3, 1), (3, 10), (3, 14),
    (7, 0), (7, 6), (7, 13),
    (10, 12), (10, 3), (10, 15)
]

print("\n--- Executing find_node plan ---")
for src_idx, target_idx in find_plan:
    if node_ids[target_idx] is None:
        print(f"Skipping find_node for target {ports[target_idx]} (no node_id)")
        continue
    try:
        result = clients[src_idx].call("find_node", node_ids[target_idx])
        print(f"Node {ports[src_idx]} searching for {ports[target_idx]} → {result}")
    except Exception as e:
        print(f"find_node error → {e}")
    time.sleep(0.5)

# 顯示每個節點的 k-bucket 狀態
print("\n--- K-BUCKET STATE ---")
for c, p in zip(clients, ports):
    try:
        buckets = c.call("show_bucket")
        print(f"{p}: {buckets}")
    except Exception as e:
        print(f"{p} → {e}")
