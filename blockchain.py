import json
import os
import random
import string
from utils import compute_hash, verify_nonce, Logger

class Block:
    def __init__(self, sender, receiver, amount, prev_hash, nonce=None):
        self.sender = str(sender)
        self.receiver = str(receiver)
        self.amount = int(amount)
        self.prev_hash = prev_hash
        self.nonce = nonce if nonce is not None else self.calculate_nonce()
        self.hash = self.compute_block_hash()
        Logger.log(self.sender, f"Block created: nonce={self.nonce}, block_hash={self.hash}, prev_hash={self.prev_hash}")

    def calculate_nonce(self):
        """
        finding nonce; sha256; hash ending in 0-4
        """
        while True:
            # random nonce
            nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            txn_string = f"{self.sender}{self.receiver}{self.amount}"
            data = f"{txn_string}{nonce}"
            h = compute_hash(data)
            
            if verify_nonce(h):
                Logger.log(self.sender, f"PoW found: nonce={nonce}, pow_hash={h}")
                return nonce

    def compute_block_hash(self):
        """
        compute hash of the entire block content
        """
        txn_string = f"{self.sender}{self.receiver}{self.amount}"
        data = f"{txn_string}{self.nonce}{self.prev_hash}"
        return compute_hash(data)
    
    def to_dict(self):
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "nonce": self.nonce,
            "prev_hash": self.prev_hash,
            "hash": self.hash
        }
    
    @staticmethod
    def from_dict(data):
        b = Block(
            data["sender"],
            data["receiver"],
            data["amount"],
            data["prev_hash"],
            nonce=data["nonce"]
        )
        
        if b.hash != data["hash"]:
            raise ValueError(f"Block hash mismatch! Data corrupted. Stored: {data['hash']}, Computed: {b.hash}")
        return b

class Blockchain:
    def __init__(self, node_id='0'):
        self.node_id = str(node_id)
        self.chain = []
        self.balance_table = {}
        self.initialize_balances()

    def initialize_balances(self):
        # nodes 1-5 start w $100
        for i in range(1, 6):
            self.balance_table[str(i)] = 100

    def get_balance(self, node_id):
        return self.balance_table.get(str(node_id), 0)

    def create_block(self, receiver, amount):
        """
        creates new block transferring money from node to reciever. 
        
        checks balances
        """
        if self.get_balance(self.node_id) < amount:
            Logger.log(self.node_id, f"Insufficient funds to send {amount}")
            return None
        
        prev_hash = self.chain[-1].hash if self.chain else "0"*64
        new_block = Block(self.node_id, receiver, amount, prev_hash)
        return new_block

    def add_block(self, block):
        """
        - updates balance table
        - returns bool based on success
        """
        # 1. check if block already exists
        for existing_block in self.chain:
            if existing_block.hash == block.hash:
                Logger.log(self.node_id, f"Block already exists in chain (hash: {block.hash[:16]}...), skipping")
                return True # if already added, then we can consider it successfull
        
        # 2. validate prev hash
        current_tip_hash = self.chain[-1].hash if self.chain else "0"*64
        if block.prev_hash != current_tip_hash:
            Logger.log(self.node_id, f"Block rejected: prev_hash mismatch. Got {block.prev_hash}, expected {current_tip_hash}")
            return False
            
        # 3. validate nonce/pow
        txn_string = f"{block.sender}{block.receiver}{block.amount}"
        pow_hash = compute_hash(f"{txn_string}{block.nonce}")
        if not verify_nonce(pow_hash):
            Logger.log(self.node_id, "Block rejected: Invalid PoW")
            return False

        # 4. validate balance
        sender_bal = self.get_balance(block.sender)
        if sender_bal < block.amount:
            Logger.log(self.node_id, f"Block rejected: Sender {block.sender} has insufficient funds ({sender_bal} < {block.amount})")
            return False
            
        # Add to chain
        self.chain.append(block)
        
        # Update Balances
        self.balance_table[block.sender] -= block.amount
        self.balance_table[block.receiver] += block.amount
        
        Logger.log(self.node_id, f"Block added: {block.sender}->{block.receiver} ${block.amount}. New Balance: {self.balance_table}")
        Logger.log(self.node_id, f"Hash pointer: {block.prev_hash} -> {block.hash}")
        return True

    def save_to_disk(self):
        filename = f"state_node_{self.node_id}.json"
        data = {
            "chain": [b.to_dict() for b in self.chain],
            "balance_table": self.balance_table
        }
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=4)
            Logger.log(self.node_id, f"State saved to {filename}")
        except Exception as e:
            Logger.log(self.node_id, f"Error saving state: {e}")

    def load_from_disk(self):
        filename = f"state_node_{self.node_id}.json"
        if not os.path.exists(filename):
            Logger.log(self.node_id, "No saved state found.")
            return

        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            
            # reconstruct chain
            self.chain = []
            for b_data in data.get("chain", []):
                self.chain.append(Block.from_dict(b_data))
                
            # Restore balance table
            self.balance_table = data.get("balance_table", {})
            self.balance_table = {str(k): v for k, v in self.balance_table.items()}
            
            Logger.log(self.node_id, f"State loaded from {filename}. Chain height: {len(self.chain)}")
        except Exception as e:
            Logger.log(self.node_id, f"Error loading state: {e}")


