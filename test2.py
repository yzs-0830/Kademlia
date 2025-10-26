import msgpackrpc, time

def new_client(ip, port):
    return msgpackrpc.Client(msgpackrpc.Address(ip, port))

# 建立節點
client_1 = new_client("127.0.0.1", 11111)
client_2 = new_client("127.0.0.1", 22222)
client_3 = new_client("127.0.0.1", 33333)



# 讓 20001 建立網路
client_1.call("create")
print("Network created on 11111")

# 讓其他節點加入
client_2.call("join", client_1.call("ping"))
print("Node 22222 joined")

client_3.call("join", client_2.call("ping"))
print("Node 33333 joined")

time.sleep(10)

# 測試 find_node
print(f"\nSearching for 33333 from node 11111...")
result1 = client_1.call("find_node", "376dd4c8375225a3d2197584de1b63831cb49d83")
print("Find node result:", result1)

print(f"\nSearching for 11111 from node 33333...")
result2 = client_3.call("find_node", "62abd6d074a0b3b9e2b6e9d2b0e8eb5bb9cd7277")
print("Find node result:", result2)

# 顯示每個節點的 kbucket 狀況
print("\n--- K-BUCKET STATE ---")
print("11111:", client_1.call("show_bucket"))
print("22222:", client_2.call("show_bucket"))
print("33333:", client_3.call("show_bucket"))
