#!/usr/bin/env python3

import json
import os
import glob
from collections import defaultdict

def load_node_state(node_id):
    """load state from a node's state file"""
    filename = f"state_node_{node_id}.json"
    if not os.path.exists(filename):
        return None
    
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return None

def verify_consistency():
    """verify all nodes have consistent state"""
    print("="*60)
    print("Consistency Checker")
    print("="*60)
    
    # Find all state files
    state_files = glob.glob("state_node_*.json")
    if not state_files:
        print("No state files found. Nodes may not have saved state yet.")
        return
    
    node_ids = sorted([f.replace("state_node_", "").replace(".json", "") 
                      for f in state_files])
    
    print(f"\nFound state files for nodes: {', '.join(node_ids)}")
    
    # Load all states
    states = {}
    for node_id in node_ids:
        state = load_node_state(node_id)
        if state:
            states[node_id] = state
    
    if len(states) == 0:
        print("No valid state files found.")
        return
    
    # Check blockchain consistency
    print("\n" + "-"*60)
    print("Blockchain Consistency Check")
    print("-"*60)
    
    blockchain_lengths = {nid: len(state['chain']) for nid, state in states.items()}
    unique_lengths = set(blockchain_lengths.values())
    
    if len(unique_lengths) == 1:
        print(f"✓ All nodes have same blockchain length: {unique_lengths.pop()}")
    else:
        print("✗ Blockchain lengths differ:")
        for nid, length in blockchain_lengths.items():
            print(f"  Node {nid}: {length} blocks")
    
    # Check if blockchains are identical
    if len(unique_lengths) == 1:
        length = unique_lengths.pop()
        blockchains_match = True
        for i in range(length):
            block_hashes = {}
            for nid, state in states.items():
                if i < len(state['chain']):
                    block_hash = state['chain'][i].get('hash', 'MISSING')
                    block_hashes[nid] = block_hash
            
            unique_hashes = set(block_hashes.values())
            if len(unique_hashes) > 1:
                print(f"\n✗ Block {i} differs across nodes:")
                for nid, h in block_hashes.items():
                    print(f"  Node {nid}: {h[:16]}...")
                blockchains_match = False
        
        if blockchains_match:
            print("✓ All nodes have identical blockchains")
    
    # Check balance consistency
    print("\n" + "-"*60)
    print("Balance Consistency Check")
    print("-"*60)
    
    all_balances = {}
    for nid, state in states.items():
        all_balances[nid] = state.get('balance_table', {})
    
    # Check each account balance across nodes
    all_accounts = set()
    for balances in all_balances.values():
        all_accounts.update(balances.keys())
    
    balances_consistent = True
    for account in sorted(all_accounts):
        account_balances = {}
        for nid, balances in all_balances.items():
            account_balances[nid] = balances.get(account, 0)
        
        unique_balances = set(account_balances.values())
        if len(unique_balances) > 1:
            print(f"✗ Account {account} balances differ:")
            for nid, bal in account_balances.items():
                print(f"  Node {nid}: ${bal}")
            balances_consistent = False
    
    if balances_consistent:
        print("✓ All nodes have identical balance tables")
        print("\nBalance Summary:")
        if all_accounts:
            sample_node = list(states.keys())[0]
            for account in sorted(all_accounts):
                balance = all_balances[sample_node].get(account, 0)
                print(f"  Account {account}: ${balance}")
    
    # Check total money
    print("\n" + "-"*60)
    print("Total Money Check")
    print("-"*60)
    
    for nid, balances in all_balances.items():
        total = sum(balances.values())
        print(f"Node {nid} total: ${total}")
    
    # Verify block structure
    print("\n" + "-"*60)
    print("Block Structure Validation")
    print("-"*60)
    
    sample_node = list(states.keys())[0]
    chain = states[sample_node]['chain']
    
    if len(chain) == 0:
        print("No blocks in chain")
    else:
        print(f"Checking {len(chain)} blocks...")
        valid = True
        prev_hash = "0" * 64
        
        for i, block in enumerate(chain):
            # Check prev_hash linkage
            if block.get('prev_hash') != prev_hash:
                print(f"✗ Block {i}: prev_hash mismatch")
                print(f"  Expected: {prev_hash}")
                print(f"  Got: {block.get('prev_hash')}")
                valid = False
            
            # Check hash ends in 0-4 (PoW)
            block_hash = block.get('hash', '')
            if block_hash and block_hash[-1] not in '01234':
                print(f"✗ Block {i}: hash does not end in 0-4")
                print(f"  Hash: {block_hash}")
                valid = False
            
            prev_hash = block.get('hash', '')
        
        if valid:
            print("✓ All blocks have valid structure")
            print("✓ All prev_hash links are correct")
            print("✓ All hashes satisfy PoW (end in 0-4)")
    
    print("\n" + "="*60)
    print("Consistency check complete!")
    print("="*60)

if __name__ == "__main__":
    verify_consistency()

