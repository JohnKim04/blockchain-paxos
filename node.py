import socket
import threading
import time
import sys
import json
from utils import load_config, Logger, compute_hash, verify_nonce
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
        self.syncing = False  # Flag to track if we're currently syncing
        self.sync_responses = []  # Store blockchain responses during sync
        
        # Paxos Instance
        self.paxos = PaxosInstance(
            node_id=self.node_id,
            num_nodes=len(self.config),
            callback_broadcast=self.broadcast,
            callback_send=self.send_msg_dict,
            callback_decide=self.handle_paxos_decision,
            get_blockchain_depth=lambda: len(self.blockchain.chain)
        )
        # Add callback to check if node is active
        self.paxos.is_node_active = lambda: not self.failed

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
        elif msg_type == 'REQUEST_BLOCKCHAIN':
            self.handle_blockchain_request(msg)
        elif msg_type == 'BLOCKCHAIN_RESPONSE':
            self.handle_blockchain_response(msg)
        else:
            Logger.log(self.node_id, f"Unknown message type: {msg_type}")

    def send_msg(self, target_id, message_str):
        """Raw string sender with delay"""
        # Don't send messages if node is failed
        if self.failed:
            return
            
        target_id = str(target_id)
        if target_id not in self.config:
            Logger.log(self.node_id, f"Unknown target {target_id}")
            return

        target_info = self.config[target_id]
        
        def _send():
            # Check again after delay (node might have failed during delay)
            if self.failed:
                return
            time.sleep(3) # 3-second delay
            # Final check before sending
            if self.failed:
                return
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
    
    def sync_blockchain(self):
        """
        Request blockchain from peers to sync after recovery.
        """
        Logger.log(self.node_id, f"Requesting blockchain from peers to sync...")
        my_depth = len(self.blockchain.chain)
        
        self.syncing = True
        self.sync_responses = []
        
        # Request blockchain from all peers
        request_msg = {
            "type": "REQUEST_BLOCKCHAIN",
            "sender": self.node_id,
            "my_depth": my_depth
        }
        self.broadcast(request_msg)
        
        # Wait for responses (with timeout)
        def wait_and_process():
            time.sleep(8)  # Wait for responses (accounting for 3s network delay)
            self.process_sync_responses()
        
        threading.Thread(target=wait_and_process).start()
    
    def handle_blockchain_request(self, msg):
        """
        Handle a request for blockchain from a recovering node.
        """
        requester_id = msg['sender']
        requester_depth = msg.get('my_depth', 0)
        my_depth = len(self.blockchain.chain)
        
        Logger.log(self.node_id, f"Received blockchain request from {requester_id} (their depth: {requester_depth}, my depth: {my_depth})")
        
        # Send our blockchain
        response_msg = {
            "type": "BLOCKCHAIN_RESPONSE",
            "sender": self.node_id,
            "chain": [b.to_dict() for b in self.blockchain.chain],
            "balance_table": self.blockchain.balance_table
        }
        self.send_msg_dict(requester_id, response_msg)
    
    def handle_blockchain_response(self, msg):
        """
        Handle blockchain response from a peer during sync.
        """
        sender_id = msg['sender']
        received_chain_data = msg.get('chain', [])
        received_balance_table = msg.get('balance_table', {})
        
        Logger.log(self.node_id, f"Received blockchain from {sender_id} (length: {len(received_chain_data)}, my length: {len(self.blockchain.chain)})")
        
        # Store response for processing
        if self.syncing:
            self.sync_responses.append({
                'sender': sender_id,
                'chain_data': received_chain_data,
                'balance_table': received_balance_table
            })
        else:
            # If not actively syncing, process immediately
            self.process_single_response(sender_id, received_chain_data, received_balance_table)
    
    def process_single_response(self, sender_id, received_chain_data, received_balance_table):
        """Process a single blockchain response immediately."""
        # Reconstruct chain from received data
        received_chain = []
        for b_data in received_chain_data:
            received_chain.append(Block.from_dict(b_data))
        
        # If received chain is longer, update our chain
        if len(received_chain) > len(self.blockchain.chain):
            Logger.log(self.node_id, f"Received longer chain from {sender_id}. Updating blockchain...")
            
            # Validate the received chain
            if self.validate_and_update_chain(received_chain, received_balance_table):
                Logger.log(self.node_id, f"Successfully synced blockchain. New length: {len(self.blockchain.chain)}")
                self.blockchain.save_to_disk()
            else:
                Logger.log(self.node_id, f"Failed to validate received chain from {sender_id}")
        elif len(received_chain) == len(self.blockchain.chain):
            Logger.log(self.node_id, f"Received chain has same length. Already up to date.")
        else:
            Logger.log(self.node_id, f"Received chain is shorter. Keeping current chain.")
    
    def process_sync_responses(self):
        """
        Process all collected sync responses and pick the longest valid chain.
        """
        if not self.sync_responses:
            Logger.log(self.node_id, "No blockchain responses received during sync.")
            self.syncing = False
            return
        
        Logger.log(self.node_id, f"Processing {len(self.sync_responses)} blockchain responses...")
        
        # Find the longest valid chain
        best_chain = None
        best_balance_table = None
        best_length = len(self.blockchain.chain)
        best_sender = None
        
        for response in self.sync_responses:
            chain_data = response['chain_data']
            balance_table = response['balance_table']
            
            if len(chain_data) > best_length:
                # Reconstruct and validate chain
                received_chain = []
                for b_data in chain_data:
                    received_chain.append(Block.from_dict(b_data))
                
                # Create a temporary blockchain to validate
                if self.validate_chain_structure(received_chain):
                    best_chain = received_chain
                    best_balance_table = balance_table
                    best_length = len(chain_data)
                    best_sender = response['sender']
        
        # Update with best chain if found
        if best_chain:
            Logger.log(self.node_id, f"Updating to longest valid chain from {best_sender} (length: {best_length})")
            if self.validate_and_update_chain(best_chain, best_balance_table):
                Logger.log(self.node_id, f"Successfully synced blockchain. New length: {len(self.blockchain.chain)}")
                self.blockchain.save_to_disk()
            else:
                Logger.log(self.node_id, f"Failed to validate best chain from {best_sender}")
        else:
            Logger.log(self.node_id, f"No longer chain found. Current chain is up to date (length: {len(self.blockchain.chain)})")
        
        self.syncing = False
        self.sync_responses = []
    
    def validate_chain_structure(self, chain):
        """Quick validation of chain structure (prev_hash links and PoW)."""
        prev_hash = "0" * 64
        for block in chain:
            if block.prev_hash != prev_hash:
                return False
            txn_string = f"{block.sender}{block.receiver}{block.amount}"
            pow_hash = compute_hash(f"{txn_string}{block.nonce}")
            if not verify_nonce(pow_hash):
                return False
            prev_hash = block.hash
        return True
    
    def validate_and_update_chain(self, new_chain, new_balance_table):
        """
        Validate a received chain and update if valid.
        Returns True if update was successful.
        """
        # Validate the entire chain
        temp_chain = []
        temp_balance_table = {}
        
        # Initialize balances
        for i in range(1, 6):
            temp_balance_table[str(i)] = 100
        
        prev_hash = "0" * 64
        
        for block_data in new_chain:
            block = Block.from_dict(block_data) if isinstance(block_data, dict) else block_data
            
            # Validate prev_hash
            if block.prev_hash != prev_hash:
                Logger.log(self.node_id, f"Chain validation failed: prev_hash mismatch at block {len(temp_chain)}")
                return False
            
            # Validate PoW
            txn_string = f"{block.sender}{block.receiver}{block.amount}"
            pow_hash = compute_hash(f"{txn_string}{block.nonce}")
            if not verify_nonce(pow_hash):
                Logger.log(self.node_id, f"Chain validation failed: invalid PoW at block {len(temp_chain)}")
                return False
            
            # Check balance before this transaction
            sender_bal = temp_balance_table.get(block.sender, 100)
            if sender_bal < block.amount:
                Logger.log(self.node_id, f"Chain validation failed: insufficient funds at block {len(temp_chain)}")
                return False
            
            # Add block
            temp_chain.append(block)
            temp_balance_table[block.sender] = sender_bal - block.amount
            temp_balance_table[block.receiver] = temp_balance_table.get(block.receiver, 100) + block.amount
            prev_hash = block.hash
        
        # If validation passed, update our chain
        self.blockchain.chain = temp_chain
        self.blockchain.balance_table = temp_balance_table
        
        return True

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
                    self.failed = True
                    # Cancel any pending Paxos proposals
                    self.paxos.cancel_proposal()

                elif cmd == "fixProcess":
                    Logger.log(self.node_id, "Simulating Recovery...")
                    self.failed = False
                    self.blockchain.load_from_disk()
                    # Sync with other nodes after recovery
                    time.sleep(1)  # Give a moment for network to be ready
                    self.sync_blockchain()

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
