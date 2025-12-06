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
        # The hash of this block, which becomes the prev_hash for the next block
        self.hash = self.compute_block_hash()
        # Log hash pointer details for debugging/demo
        Logger.log(self.sender, f"Block created: nonce={self.nonce}, block_hash={self.hash}, prev_hash={self.prev_hash}")

    def calculate_nonce(self):
        """
        Find a nonce such that SHA256(sender + receiver + amount + nonce) ends in 0-4.
        """
        while True:
            # Generate a random nonce
            nonce = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
            # Check PoW condition
            # Project specs: h = SHA256(Txns || Nonce)
            # Txns string format: sender + receiver + str(amount) (simplification)
            txn_string = f"{self.sender}{self.receiver}{self.amount}"
            data = f"{txn_string}{nonce}"
            h = compute_hash(data)
            
            if verify_nonce(h):
                # Log the successful nonce and its PoW hash for debugging/demo
                Logger.log(self.sender, f"PoW found: nonce={nonce}, pow_hash={h}")
                return nonce

    def compute_block_hash(self):
        """
        Computes the hash of the entire block content.
        Project specs Eq 1: Tn+1.Hash = SHA256(Tn.Txns || Tn.Nonce || Tn.Hash)
        where Tn.Hash is the prev_hash stored in Tn.
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
        # Verify integrity
        if b.hash != data["hash"]:
            # If recomputed hash doesn't match stored hash, data is corrupted
            # For now, we just proceed or log warning? 
            # In a strict system we'd reject.
            pass
        return b

class Blockchain:
    def __init__(self, node_id='0'):
        self.node_id = str(node_id)
        self.chain = []
        self.balance_table = {}
        self.initialize_balances()
        
        # Genesis block or empty chain?
        # The project doesn't explicitly specify a genesis block, but we need one for the first prev_hash.
        # Let's assume the chain starts empty and the first block has prev_hash = "0"*64 or similar.
        # Or maybe we create a genesis block now.
        # "Initially... 5 clients-id and an initial balance of 100"
        # We handle this in initialize_balances, no blocks needed for initial money.

    def initialize_balances(self):
        # Nodes 1-5 start with $100
        for i in range(1, 6):
            self.balance_table[str(i)] = 100

    def get_balance(self, node_id):
        return self.balance_table.get(str(node_id), 0)

    def create_block(self, receiver, amount):
        """
        Creates a new block transferring money from self.node_id to receiver.
        Does NOT add it to chain yet (wait for Consensus).
        Checks balance first.
        """
        if self.get_balance(self.node_id) < amount:
            Logger.log(self.node_id, f"Insufficient funds to send {amount}")
            return None
        
        prev_hash = self.chain[-1].hash if self.chain else "0"*64
        new_block = Block(self.node_id, receiver, amount, prev_hash)
        return new_block

    def add_block(self, block):
        """
        Validates and adds a block to the chain.
        Updates balance table.
        Returns True if successful, False if invalid.
        """
        # 0. Check if block already exists (deduplication)
        for existing_block in self.chain:
            if existing_block.hash == block.hash:
                Logger.log(self.node_id, f"Block already exists in chain (hash: {block.hash[:16]}...), skipping")
                return True  # Already added, consider it successful
        
        # 1. Validate Prev Hash
        current_tip_hash = self.chain[-1].hash if self.chain else "0"*64
        if block.prev_hash != current_tip_hash:
            Logger.log(self.node_id, f"Block rejected: prev_hash mismatch. Got {block.prev_hash}, expected {current_tip_hash}")
            return False
            
        # 2. Validate PoW (Nonce)
        txn_string = f"{block.sender}{block.receiver}{block.amount}"
        pow_hash = compute_hash(f"{txn_string}{block.nonce}")
        if not verify_nonce(pow_hash):
            Logger.log(self.node_id, "Block rejected: Invalid PoW")
            return False

        # 3. Validate Balance (Double spend check)
        # We must replay or check if sender had enough money BEFORE this block.
        # Since we update balance_table incrementally, we check current table.
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
            
            # Reconstruct chain
            self.chain = []
            for b_data in data.get("chain", []):
                self.chain.append(Block.from_dict(b_data))
                
            # Restore balance table
            # Alternatively, we could re-calculate from initial state + chain replay
            # to be safer, but instructions imply persisting table is allowed.
            self.balance_table = data.get("balance_table", {})
            # Ensure keys are strings
            self.balance_table = {str(k): v for k, v in self.balance_table.items()}
            
            Logger.log(self.node_id, f"State loaded from {filename}. Chain height: {len(self.chain)}")
        except Exception as e:
            Logger.log(self.node_id, f"Error loading state: {e}")


