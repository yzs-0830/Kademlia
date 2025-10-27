import msgpackrpc, time

def new_client(ip, port):
    return msgpackrpc.Client(msgpackrpc.Address(ip, port))

# 建立節點 20001 ~ 20008
client_1 = new_client("127.0.0.1", 20001)
client_2 = new_client("127.0.0.1", 20002)
client_3 = new_client("127.0.0.1", 20003)
client_4 = new_client("127.0.0.1", 20004)
client_5 = new_client("127.0.0.1", 20005)
client_6 = new_client("127.0.0.1", 20006)
client_7 = new_client("127.0.0.1", 20007)
client_8 = new_client("127.0.0.1", 20008)

# 讓 20001 建立網路
client_1.call("create")
print("Network created on 20001")

# 其他節點加入
client_2.call("join", client_1.call("ping"))
print("Node 20002 joined")

client_3.call("join", client_2.call("ping"))
print("Node 20003 joined")

client_4.call("join", client_1.call("ping"))
print("Node 20004 joined")

client_5.call("join", client_3.call("ping"))
print("Node 20005 joined")

client_6.call("join", client_4.call("ping"))
print("Node 20006 joined")

client_7.call("join", client_2.call("ping"))
print("Node 20007 joined")

client_8.call("join", client_5.call("ping"))
print("Node 20008 joined")

# 等一下讓節點更新 k-bucket
time.sleep(2)



# 測試 find_node (5 次查詢，避免查詢 join 相鄰點)

print(f"\nSearching for 20005 from node 20001...")
result1 = client_1.call("find_node", "b343b0f2536a2c373a0992247c07d55415bb4261")
print("Find node result:", result1)
time.sleep(1)

print(f"\nSearching for 20008 from node 20002...")
result2 = client_2.call("find_node", "c093d3599f124a5b370c9b8b857fdad372cceb77")
print("Find node result:", result2)
time.sleep(1)

print(f"\nSearching for 20006 from node 20003...")
result3 = client_3.call("find_node", "559674cb3992337b56a02644e641630878252e9d")
print("Find node result:", result3)
time.sleep(1)

print(f"\nSearching for 20003 from node 20004...")
result4 = client_4.call("find_node", "0abb48e18a649835e7c8ca37bde0782fb252b607")
print("Find node result:", result4)
time.sleep(1)


print(f"\nSearching for 20001 from node 20007...")
result5 = client_7.call("find_node", "bcc603d8b8fbea8dc2db809a1d1ea9546680b247")
print("Find node result:", result5)


# 顯示每個節點的 kbucket 狀況
print("\n--- K-BUCKET STATE ---")
print("20001:", client_1.call("show_bucket"))
print("20002:", client_2.call("show_bucket"))
print("20003:", client_3.call("show_bucket"))
print("20004:", client_4.call("show_bucket"))
print("20005:", client_5.call("show_bucket"))
print("20006:", client_6.call("show_bucket"))
print("20007:", client_7.call("show_bucket"))
print("20008:", client_8.call("show_bucket"))
