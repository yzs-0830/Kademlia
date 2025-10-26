import msgpackrpc
import time
import hashlib

def new_client(ip, port):
    return msgpackrpc.Client(msgpackrpc.Address(ip, port))

def sha1_of(ip, port):
    return hashlib.sha1(f"{ip}:{port}".encode()).hexdigest()

ip = "127.0.0.1"
ports = list(range(11101, 11117))
clients = [new_client(ip, p) for p in ports]

print("=== Network creation ===")
clients[0].call("create")
print(f"Network created on {ports[0]}")
time.sleep(2)

# 逐個加入（不全部從同一個節點加入）
print("\n=== Joining phase ===")
for i in range(1, len(clients)):
    bootstrap_index = max(0, i - 2)  # 每個節點從前兩個之一加入
    try:
        clients[i].call("join", clients[bootstrap_index].call("ping"))
        print(f"Node {ports[i]} joined via {ports[bootstrap_index]}")
    except Exception as e:
        print(f"Join failed for {ports[i]} → {e}")
    time.sleep(2)  # join 後停 2 秒

time.sleep(20)

# 多次 find_node 測試
print("\n=== find_node tests ===")
targets = [11103, 11108, 11114]
for t in targets:
    key = sha1_of(ip, t)
    for cport, client in zip(ports[:5], clients[:5]):  # 前五個節點各查一個目標
        try:
            print(f"\n[{cport}] Searching for node {t} (key={key[:6]}...)")
            result = client.call("find_node", key)  # 不帶 timeout
            print("Result:", result)
        except Exception as e:
            print(f"[{cport}] find_node error → {e}")
        time.sleep(2)  # 查找後停 2 秒

# 顯示所有 bucket 狀態
print("\n=== K-BUCKET STATES ===")
for port, client in zip(ports, clients):
    try:
        buckets = client.call("show_bucket")
        print(f"{port}:", buckets)
    except Exception as e:
        print(f"{port} → {e}")
