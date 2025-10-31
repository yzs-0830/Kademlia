# Kademlia Node Implementation

這是一個基於 Python 的 Kademlia 節點實作，提供分散式哈希表 (DHT) 節點的建立、加入網路、查詢節點以及節點健康檢查功能。

## 功能概覽

* **建立節點**：使用 IP 和 Port 進行 SHA-1 生成 Node ID。
* **加入網路**：透過已知節點加入 Kademlia 網路。
* **查找節點**：使用 XOR 距離算法查找最近的節點。
* **節點健康檢查**：背景自動 ping 所有節點，維護活躍節點列表。
* **節點替換策略**：自動將失效節點替換為候補節點（replacement cache）。

---

## 啟動方式

### Python 執行方式

```bash
python kad.py <ip> <port>
```

### 編譯後執行檔方式 (Linux / Mac)

```bash
./kad <ip> <port>
```

**範例**：

```bash
python kad.py 127.0.0.1 20001
./kad 127.0.0.1 20001
```

---

## 可調整核心參數

* `search_node_per_round`：每輪查找發送的節點數量。
* `search_round_max`：查找的最大輪數。
* `send_back_node`：`send_closest` 每次返回的節點數量。
* `total_k`：整個 k-bucket 的最大節點數量。
* `k_value`：單個 bucket 的最大節點數。
* `remove_limit`：節點失敗 ping 次數上限，超過則替換。
* `check_interval`：背景健康檢查的間隔秒數。
* `join_buffer`：節點加入網路後等待啟動 ping 檢查的緩衝時間。

---

## 節點方法說明

| 方法                             | 功能                         |
| ------------------------------ | -------------------------- |
| `ping()`                       | 回傳節點自身 IP、Port 與 Node ID   |
| `create()`                     | 建立空的 k-bucket，初始化網路        |
| `start_auto_ping()`            | 啟動背景自動 ping 節點檢查           |
| `check_nodes()`                | 背景檢查節點健康狀況，替換失效節點          |
| `join(contact)`                | 加入網路，透過指定 contact 節點進行初始查找 |
| `find_node(key)`               | 根據 key 查找最近節點，採取階段性擴散查找策略  |
| `join_find(key)`               | 加入網路時查找自身位置（初始查找使用）        |
| `send_closest(key)`            | 回傳 k 個距離指定 key 最近的節點給其他節點  |
| `kill()`                       | 結束節點程式                     |
| `add_node(node_info)`          | 將新節點加入 k-bucket 或候補 cache  |
| `replace_dead_node(dead_node)` | 替換失效節點，或將其標記為 inactive     |

---

## 節點運作概念

1. **候選池 (results)**

   * 查找過程中暫存所有已知節點，並控制每輪查詢數量 (`per_round`)。
   * 節點只查詢部分候選節點，但候選池中保存了更多節點，提高成功率。

2. **階段性擴散**

   * 前期查詢略多節點以快速擴散網路資訊。
   * 後期查詢逐步收斂，控制訊息複雜度。

3. **替換策略**

   * k-bucket 滿時，額外節點存入 `replacement_cache`。
   * 失效節點會被候補節點替換，保持網路穩定性。

---

## 依賴套件

* `msgpackrpc`：節點間 RPC 通訊
* Python 標準庫：`hashlib`, `os`, `threading`, `time`, `random`

安裝 RPC 套件：

```bash
pip install msgpack-rpc-python
```

---

## 注意事項

* 節點需保證 port 可用且互相可連線。
* 背景 ping 檢查會持續運作，若進行調整請確保 `join_buffer` 與 `check_interval` 合理設定。
* 目前每個 bucket 的大小 (`k_value`) 與總大小 (`total_k`) 影響網路覆蓋率與訊息複雜度，目前版本在維持 `total_k` = 4 和 `k_value` = 1 下可能因加入方式影響正確率。

