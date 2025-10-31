# test_plan_manual.py
import time
import msgpackrpc
import hashlib

IP = "127.0.0.1"
PORTS = list(range(20001, 20017))  # 20001..20016 (16 nodes)

def parent_port(port):
    idx = port - 20000
    parent_idx = idx - 1
    return 20000 + parent_idx if parent_idx >= 1 else None

FIND_PAIRS_PHASE1 = [
    (20001, 20007),
    (20007, 20002),
    (20009, 20014),
    (20002, 20010),
    (20004, 20013),
    (20008, 20003),
    (20015, 20001),
]


FIND_PAIRS_PHASE2 = [
    (20007, 20015),
    (20004, 20012),
    (20006, 20014),
    (20008, 20016),
    (20009, 20003),
    (20012, 20007),
    (20013, 20006),
]

KILL_PLAN = [20005, 20010]  # 先 kill 兩個節點
FINAL_KILL = [20001, 20002, 20003, 20004, 20006, 20007, 20008, 20009, 20011, 20012, 20013, 20014, 20015, 20016]
alive_ports = [p for p in PORTS if p not in KILL_PLAN]

def client(port):
    return msgpackrpc.Client(msgpackrpc.Address(IP, port))

def node_id_of(port):
    try:
        return client(port).call("ping")[b"node_id"].decode()
    except Exception:
        return None

def show_all_buckets():
    print("\n=== K-BUCKET STATES ===")
    for port in PORTS:
        try:
            buckets = client(port).call("show_bucket")
            print(f"{port}: {buckets}")
        except Exception as e:
            print(f"{port} → {e}")
    print("=== END OF K-BUCKET STATES ===\n")

def join_phase_all():
    print("=== Join Phase: binary-tree 加入 (20002..20016) ===")
    for port in PORTS[1:]:
        p = parent_port(port)
        if p is None:
            continue
        print(f"[Join] Node {port} -> join via {p}")
        try:
            c_target = client(port)
            c_parent = client(p)
            parent_info = c_parent.call("ping")
            c_target.call("join", parent_info)
            print(f"  OK: {port} joined via {p}")
        except Exception as e:
            print(f"  !! join failed for {port} via {p} → {e}")
        time.sleep(2)
    print("=== Join Phase Done ===")

def find_phase(pairs, phase_name):
    print(f"\n=== Find Phase ({phase_name}) start: {len(pairs)} queries ===")
    for (src, dst) in pairs:
        print(f"[Find] {src} -> find node_id of {dst}")
        dst_id = node_id_of(dst)
        if not dst_id:
            print(f"  !! cannot get node_id of {dst}, skip")
            time.sleep(2)
            continue
        try:
            c = client(src)
            res = c.call("find_node", dst_id)
            print(f"  → Result from {src}: {res}")
        except Exception as e:
            print(f"  → find_node error from {src} → {e}")
        time.sleep(2)
    print(f"=== Find Phase ({phase_name}) done ===")
    show_all_buckets()  # ← 每次 find 後顯示 bucket 狀態

def kill_phase(kill_list):
    print("\n=== Kill Phase start ===")
    killed = []
    for idx, port in enumerate(kill_list):
        if idx >= 2:
            break
        print(f"[Kill] attempt kill node {port}")
        try:
            c = client(port)
            try:
                c.call("kill")
                print(f"  → kill RPC returned for {port}")
            except Exception as e:
                print(f"  → kill RPC error/timeout for {port}: {e}")
        except Exception as e:
            print(f"  !! Cannot reach node {port} → {e}")
        killed.append(port)
        time.sleep(10)
    print("=== Kill Phase done ===")
    return killed

def final_kill_phase(kill_list):
    print("\n=== Final Kill Phase start ===")
    killed = []
    for idx, port in enumerate(kill_list):
        if idx >= 14:
            break
        print(f"[Kill] attempt kill node {port}")
        try:
            c = client(port)
            try:
                c.call("kill")
                print(f"  → kill RPC returned for {port}")
            except Exception as e:
                print(f"  → kill RPC error/timeout for {port}: {e}")
        except Exception as e:
            print(f"  !! Cannot reach node {port} → {e}")
        killed.append(port)
    print("=== Final Kill Phase done ===")
    return killed

def rejoin_phase(targets, alive_ports, bootstrap_port=20001):
    print("\n=== Re-Join Phase ===")
    for port in targets:
        p = parent_port(port)
        # 若 parent 不存在或 parent 死了，就往上找一個活的 parent
        while p not in alive_ports and p is not None:
            p = parent_port(p)

        # 如果整條線都死光，就用 bootstrap node
        if p is None or p not in alive_ports:
            p = bootstrap_port

        print(f"[Re-Join] Node {port} → via {p}")
        try:
            c_target = client(port)
            c_parent = client(p)
            parent_info = c_parent.call("ping")
            c_target.call("join", parent_info)
            print(f"  OK: {port} rejoined via {p}")
        except Exception as e:
            print(f"  !! rejoin failed for {port} → {e}")
        time.sleep(2)
    print("=== Re-Join Phase done ===")


if __name__ == "__main__":
    print("=== TEST PLAN START ===")
    join_phase_all()

    print("等待 20 秒 (join→find)...")
    time.sleep(5)
    find_phase(FIND_PAIRS_PHASE1, "Phase1")

    print("等待 2 秒 (find→kill)...")
    time.sleep(2)
    killed = kill_phase(KILL_PLAN)

    print("等待 20 秒 (kill cooldown)...")
    time.sleep(20)
    find_phase(FIND_PAIRS_PHASE2, "Phase2")

    final_killed = final_kill_phase(FINAL_KILL)
    print("=== TEST PLAN END ===")
