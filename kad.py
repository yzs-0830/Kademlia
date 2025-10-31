import msgpackrpc
import sys
import hashlib
from Knode import KademliaNode

def get_config(): #read ip, port and generate node_id
    if len(sys.argv) != 3:
        sys.exit(1)

    ip = sys.argv[1]
    port = int(sys.argv[2])
    node_string = ip + str(port)
    node_id = hashlib.sha1(node_string.encode('utf-8')).hexdigest()  # 40-digit SHA-1

    return ip, port, node_id


if __name__ == "__main__":
    MyIP, MyPort, MyNodeID = get_config()

    # create RPC server
    node = KademliaNode(MyIP, MyPort, MyNodeID)
    server = msgpackrpc.Server(node)
    server.listen(msgpackrpc.Address(MyIP, MyPort))
    print(f"Kademlia node listening on {MyIP}:{MyPort}")
    server.start()

