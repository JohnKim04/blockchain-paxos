import socket
import threading
import time
import sys
import json
from utils import load_config, Logger
from blockchain import Blockchain, Block
from paxos import PaxosInstance

class Node:
    def __init__(self, node_id):
        self.node_id = str(node_id)
        self.config = load_config()
        
        if self.node_id not in self.config:
            print(f"Error: Node ID {self.node_id} not found in config.")
            sys.exit(1)
            
        self.info = self.config[self.node_id]
        self.port = self.info['port']
        self.ip = self.info['ip']
        self.peers = [nid for nid in self.config if nid != self.node_id]
        
        # Blockchain & Paxos
        self.blockchain = Blockchain(self.node_id)
        # Try to load existing state
        self.blockchain.load_from_disk()

        self.failed = False # Simulation flag
        
        # Paxos Instance
        self.paxos = PaxosInstance(
            node_id=self.node_id,
            num_nodes=len(self.config),
            callback_broadcast=self.broadcast,
            callback_send=self.send_msg_dict,
            callback_decide=self.handle_paxos_decision,
            get_blockchain_depth=lambda: len(self.blockchain.chain)
        )

        # Server socket
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_sock.bind((self.ip, self.port))
            self.server_sock.listen(5)
        except OSError as e:
            print(f"Error binding to {self.ip}:{self.port}: {e}")
            sys.exit(1)
            
        Logger.log(self.node_id, f"Listening on {self.ip}:{self.port}")
        
        # Threads
        self.running = True
        self.listen_thread = threading.Thread(target=self.accept_connections)
        self.listen_thread.daemon = True
        self.listen_thread.start()
        
        self.cli_thread = threading.Thread(target=self.handle_cli)
        self.cli_thread.daemon = True
        self.cli_thread.start()

    def accept_connections(self):
        while self.running:
            try:
                client, address = self.server_sock.accept()
                threading.Thread(target=self.handle_incoming_message, args=(client,)).start()
            except OSError:
                break
            except Exception as e:
                Logger.log(self.node_id, f"Error accepting connection: {e}")

    def handle_incoming_message(self, conn):
        try:
            if self.failed:
                conn.close()
                return

            data = b""
            while True:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk
            
            if not data:
                return

            message_str = data.decode('utf-8')
            # Messages can be concatenated? JSON decode might fail if multiple.
            # Assuming one connection per message for simplicity (short-lived connections)
            # as implemented in send_msg.
            
            try:
                msg = json.loads(message_str)
                self.process_message(msg)
            except json.JSONDecodeError:
                Logger.log(self.node_id, f"Received invalid JSON: {message_str}")
                
        except Exception as e:
            Logger.log(self.node_id, f"Error handling message: {e}")
        finally:
            conn.close()

    def process_message(self, msg):
        msg_type = msg.get('type')
        Logger.log(self.node_id, f"Received {msg_type} from {msg.get('sender')}")
        
        if msg_type == 'PREPARE':
            self.paxos.handle_prepare(msg)
        elif msg_type == 'PROMISE':
            self.paxos.handle_promise(msg)
        elif msg_type == 'ACCEPT':
            self.paxos.handle_accept(msg)
        elif msg_type == 'ACCEPTED':
            self.paxos.handle_accepted(msg)
        elif msg_type == 'DECIDE':
            self.paxos.handle_decide(msg)
        else:
            Logger.log(self.node_id, f"Unknown message type: {msg_type}")

    def send_msg(self, target_id, message_str):
        """Raw string sender with delay"""
        target_id = str(target_id)
        if target_id not in self.config:
            Logger.log(self.node_id, f"Unknown target {target_id}")
            return

        target_info = self.config[target_id]
        
        def _send():
            time.sleep(3) # 3-second delay
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((target_info['ip'], target_info['port']))
                s.sendall(message_str.encode('utf-8'))
                s.close()
                # Logger.log(self.node_id, f"Sent to {target_id}: {message_str[:50]}...")
            except ConnectionRefusedError:
                # Logger.log(self.node_id, f"Failed to connect to Node {target_id} (Connection Refused)")
                pass
            except Exception as e:
                Logger.log(self.node_id, f"Failed to send to {target_id}: {e}")

        threading.Thread(target=_send).start()

    def send_msg_dict(self, target_id, msg_dict):
        """Helper to send dict as JSON"""
        self.send_msg(target_id, json.dumps(msg_dict))

    def broadcast(self, msg_dict):
        """Send to all OTHER nodes"""
        json_msg = json.dumps(msg_dict)
        for pid in self.peers:
            self.send_msg(pid, json_msg)

    def handle_paxos_decision(self, block_data):
        """
        Callback from Paxos when a block is decided.
        """
        if not block_data:
            return
            
        block = Block.from_dict(block_data)
        
        # Add to blockchain
        if self.blockchain.add_block(block):
            self.blockchain.save_to_disk()
            Logger.log(self.node_id, f"Block committed. New chain height: {len(self.blockchain.chain)}")
        else:
            Logger.log(self.node_id, f"Failed to add decided block (validation error).")

    def handle_cli(self):
        print(f"Node {self.node_id} CLI ready.")
        print("Commands: moneyTransfer <dest> <amt>, failProcess, fixProcess, printBlockchain, printBalance, exit")
        
        while self.running:
            try:
                user_input = input()
                if not user_input:
                    continue
                    
                parts = user_input.strip().split()
                cmd = parts[0]
                
                if cmd == "moneyTransfer" and len(parts) == 3:
                    if self.failed:
                        print("Cannot process command: Node is failed.")
                        continue
                        
                    dest = parts[1]
                    amt = int(parts[2])
                    
                    # 1. Create Block
                    block = self.blockchain.create_block(dest, amt)
                    if block:
                        Logger.log(self.node_id, f"Initiating Paxos for block: {block.sender}->{block.receiver} ${block.amount}")
                        # 2. Start Paxos
                        self.paxos.prepare(block)
                    else:
                        print("Transaction failed (insufficient funds?)")
                        
                elif cmd == "failProcess":
                    Logger.log(self.node_id, "Simulating Crash...")
                    # In a real crash, we stop threads. 
                    # For simulation, we can just set a flag in Node/Paxos to ignore messages?
                    # Instructions: "If self.failed == True, listen_thread drops all incoming..."
                    # I'll implement this if requested, for now just logging.
                    # Wait, Phase 4 requires this. I'll add a 'failed' flag now.
                    self.failed = True # TODO: Check this flag in listen thread

                elif cmd == "fixProcess":
                    Logger.log(self.node_id, "Simulating Recovery...")
                    self.failed = False
                    self.blockchain.load_from_disk()

                elif cmd == "printBlockchain":
                    print(json.dumps([b.to_dict() for b in self.blockchain.chain], indent=2))
                    
                elif cmd == "printBalance":
                    print(self.blockchain.balance_table)

                elif cmd == "exit":
                    self.running = False
                    self.server_sock.close()
                    sys.exit(0)
                else:
                    print("Unknown command.")
            except EOFError:
                # CLI input closed, stop CLI loop but keep node running
                break
            except Exception as e:
                Logger.log(self.node_id, f"CLI Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 node.py <node_id>")
        sys.exit(1)
    
    node_id = sys.argv[1]
    node = Node(node_id)
    
    try:
        while node.running:
            time.sleep(1)
    except KeyboardInterrupt:
        node.running = False
        node.server_sock.close()
        sys.exit(0)
