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
        # join 時直接傳 bootstrap node 的地址，不自動 find(self)
        bootstrap_info = clients[bootstrap_index].call("ping")
        clients[i].call("join", bootstrap_info)
        print(f"Node {ports[i]} joined via {ports[bootstrap_index]}")
    except Exception as e:
        print(f"Join failed for {ports[i]} → {e}")
    time.sleep(1)  # join 間隔短一些

# 多次 find_node 測試
print("\n=== find_node tests ===")
targets = [11103, 11108, 11114]
for t in targets:
    key = sha1_of(ip, t)
    for cport, client in zip(ports[:5], clients[:5]):
        print(f"\n[{cport}] Searching for node {t} (key={key[:6]}...)")
        result = None
        for attempt in range(3):  # 重試三次
            try:
                result = client.call("find_node", key, timeout=5)
                break
            except Exception:
                time.sleep(0.5)
        if result:
            print("Result:", result)
        else:
            print(f"[{cport}] find_node error → Request timed out")

# 顯示所有 bucket 狀態
print("\n=== K-BUCKET STATES ===")
for port, client in zip(ports, clients):
    try:
        buckets = client.call("show_bucket")
        print(f"{port}:", buckets)
    except Exception as e:
        print(f"{port} → {e}")

