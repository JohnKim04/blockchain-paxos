#!/usr/bin/env python3
"""
Test guide and helper for blockchain-paxos system.
This script provides step-by-step testing instructions.

NOTE: Nodes accept commands via stdin (CLI), not TCP. 
You'll need to manually type commands in each node's terminal.
This script provides a guided checklist for testing.
"""

import time
import sys

class TestRunner:
    def wait(self, seconds):
        """Wait and print progress"""
        print(f"\n⏳ Waiting {seconds} seconds for consensus...")
        print("   (Watch the node terminals for Paxos messages)")
        for i in range(seconds):
            time.sleep(1)
            if (i + 1) % 5 == 0:
                print(f"   {i+1}/{seconds} seconds elapsed")
    
    def test_sequential_transfers(self):
        """Test 1: Sequential transfers"""
        print("\n" + "="*60)
        print("TEST 1: Sequential Transfers")
        print("="*60)
        
        print("\n📝 MANUAL STEPS:")
        print("   1. In Node 1 terminal, type: moneyTransfer 2 30")
        print("   2. Press Enter")
        input("\n   Press Enter after you've sent the command...")
        
        self.wait(25)  # Wait for consensus
        
        print("\n📝 Next step:")
        print("   3. In Node 2 terminal, type: moneyTransfer 3 20")
        print("   4. Press Enter")
        input("\n   Press Enter after you've sent the command...")
        
        self.wait(25)
        
        print("\n✓ Test 1 complete. Now verify:")
        print("   On ALL nodes, type:")
        print("   - printBlockchain")
        print("   - printBalance")
        print("\n   ✓ All nodes should have identical state")
        print("   ✓ Node 1: $70, Node 2: $110, Node 3: $120")
    
    def test_concurrent_transfers(self):
        """Test 2: Concurrent transfers"""
        print("\n" + "="*60)
        print("TEST 2: Concurrent Transfers (Multiple Leaders)")
        print("="*60)
        
        print("\n📝 MANUAL STEPS (do these QUICKLY, within 1-2 seconds):")
        print("   1. In Node 1 terminal: moneyTransfer 2 10")
        print("   2. In Node 3 terminal: moneyTransfer 4 15")
        print("   3. In Node 5 terminal: moneyTransfer 1 20")
        print("\n   Type all three commands quickly, then press Enter here...")
        input()
        
        print("\n⏳ Waiting for all consensus rounds to complete...")
        self.wait(45)
        
        print("\n✓ Test 2 complete. Now verify:")
        print("   On ALL nodes, type:")
        print("   - printBlockchain")
        print("   - printBalance")
        print("\n   ✓ All nodes should have 3 blocks")
        print("   ✓ All nodes should have identical blockchains")
        print("   ✓ Total money should still be $500")
    
    def test_insufficient_funds(self):
        """Test 3: Insufficient funds"""
        print("\n" + "="*60)
        print("TEST 3: Insufficient Funds")
        print("="*60)
        
        print("\n📝 MANUAL STEP:")
        print("   In Node 1 terminal, type: moneyTransfer 2 150")
        print("   (Node 1 only has $100, so this should fail)")
        input("\n   Press Enter after you've sent the command...")
        
        self.wait(5)
        
        print("\n✓ Test 3 complete. Check Node 1 output:")
        print("   ✓ Should show 'Transaction failed (insufficient funds?)'")
        print("   ✓ No block should be created")
        print("   ✓ All balances should still be $100")
    
    def test_node_failure(self):
        """Test 4: Single node failure"""
        print("\n" + "="*60)
        print("TEST 4: Single Node Failure (Non-Leader)")
        print("="*60)
        
        print("\n📝 Step 1: Normal transaction")
        print("   In Node 1 terminal: moneyTransfer 2 30")
        input("   Press Enter after sending command...")
        
        self.wait(25)
        
        print("\n📝 Step 2: Fail Node 3")
        print("   In Node 3 terminal: failProcess")
        input("   Press Enter after sending command...")
        
        self.wait(2)
        
        print("\n📝 Step 3: Transaction with 4 nodes")
        print("   In Node 2 terminal: moneyTransfer 4 20")
        input("   Press Enter after sending command...")
        
        self.wait(25)
        
        print("\n📝 Step 4: Recover Node 3")
        print("   In Node 3 terminal: fixProcess")
        input("   Press Enter after sending command...")
        
        self.wait(10)
        
        print("\n✓ Test 4 complete. Check Node 3:")
        print("   - printBlockchain (should have 2 blocks)")
        print("   - printBalance (should match other nodes)")
    
    def test_leader_failure(self):
        """Test 5: Leader failure during consensus"""
        print("\n" + "="*60)
        print("TEST 5: Leader Failure During Consensus")
        print("="*60)
        
        print("\n📝 Step 1: Start transaction on Node 1")
        print("   In Node 1 terminal: moneyTransfer 2 30")
        input("   Press Enter after sending command...")
        
        time.sleep(1)
        
        print("\n📝 Step 2: IMMEDIATELY fail Node 1 (leader)")
        print("   In Node 1 terminal: failProcess")
        print("   (Do this within 1-2 seconds of step 1)")
        input("   Press Enter after sending command...")
        
        self.wait(30)  # Wait for timeout
        
        print("\n📝 Step 3: New transaction from Node 2")
        print("   In Node 2 terminal: moneyTransfer 3 20")
        input("   Press Enter after sending command...")
        
        self.wait(25)
        
        print("\n📝 Step 4: Recover Node 1")
        print("   In Node 1 terminal: fixProcess")
        input("   Press Enter after sending command...")
        
        self.wait(10)
        
        print("\n✓ Test 5 complete. Check all nodes:")
        print("   - System should have made progress")
        print("   - Node 1 should have synced after recovery")

    def test_partition(self):
        """Test 7: Network partition (minority vs majority)"""
        print("\n" + "="*60)
        print("TEST 7: Network Partition (Minority vs Majority)")
        print("="*60)

        print("\n📝 Partition setup (two islands):")
        print("   Group A: Nodes 1,2   |   Group B: Nodes 3,4,5")
        print("   In Node 1 terminal: failLink 3 ; failLink 4 ; failLink 5")
        print("   In Node 2 terminal: failLink 3 ; failLink 4 ; failLink 5")
        print("   In Node 3 terminal: failLink 1 ; failLink 2")
        print("   In Node 4 terminal: failLink 1 ; failLink 2")
        print("   In Node 5 terminal: failLink 1 ; failLink 2")
        input("\n   Press Enter after partition is configured on all nodes...")

        print("\n📝 Step A (Minority failure expected):")
        print("   In Node 1 terminal: moneyTransfer 2 10")
        print("   Expected: hangs/times out (no quorum, only 2/5 reachable)")
        input("   Press Enter after sending command...")
        self.wait(30)

        print("\n📝 Step B (Majority success expected):")
        print("   In Node 3 terminal: moneyTransfer 4 10")
        print("   Expected: succeeds (quorum 3/5 reachable)")
        input("   Press Enter after sending command...")
        self.wait(30)

        print("\n📝 Step C: Heal partition on all nodes")
        print("   Run on each node: fixLink all")
        input("   Press Enter after healing all links...")
        self.wait(8)

        print("\n📝 Step D: Verify sync")
        print("   On ALL nodes, type:")
        print("   - printBlockchain")
        print("   - printBalance")
        print("   Expected: Nodes 1 and 2 have learned the block(s) from the majority.")
        print("\n✓ Test 7 complete.")
    
    def test_multiple_node_failure(self):
        """Test 6: Multiple node failures (2 nodes)"""
        print("\n" + "="*60)
        print("TEST 6: Multiple Node Failures (2 Nodes)")
        print("="*60)
        
        print("\n📝 Step 1: Fail 2 nodes (Node 4 and Node 5)")
        print("   In Node 4 terminal: failProcess")
        print("   In Node 5 terminal: failProcess")
        print("   (Fail both nodes)")
        input("   Press Enter after failing both nodes...")
        
        self.wait(2)
        
        print("\n📝 Step 2: Transaction with 3 remaining nodes")
        print("   System should still work (majority = 3 out of 5)")
        print("   In Node 1 terminal: moneyTransfer 2 30")
        input("   Press Enter after sending command...")
        
        self.wait(25)
        
        print("\n📝 Step 3: Another transaction with 3 nodes")
        print("   In Node 2 terminal: moneyTransfer 3 20")
        input("   Press Enter after sending command...")
        
        self.wait(25)
        
        print("\n📝 Step 4: Recover Node 4")
        print("   In Node 4 terminal: fixProcess")
        input("   Press Enter after sending command...")
        
        self.wait(5)
        
        print("\n📝 Step 5: Recover Node 5")
        print("   In Node 5 terminal: fixProcess")
        input("   Press Enter after sending command...")
        
        self.wait(10)
        
        print("\n✓ Test 6 complete. Now verify:")
        print("   On ALL nodes, type:")
        print("   - printBlockchain")
        print("   - printBalance")
        print("\n   ✓ All nodes should have 2 blocks")
        print("   ✓ All nodes should have identical blockchains")
        print("   ✓ Node 4 and Node 5 should have synced after recovery")
        print("   ✓ System should have continued with 3 nodes (majority)")
    
    def cleanup_state(self):
        """Clean up state files"""
        import os
        import glob
        state_files = glob.glob("state_node_*.json")
        for f in state_files:
            try:
                os.remove(f)
                print(f"Removed {f}")
            except:
                pass

def main():
    runner = TestRunner()
    
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        print("Cleaning state files...")
        runner.cleanup_state()
        return
    
    print("="*60)
    print("Blockchain-Paxos Test Guide")
    print("="*60)
    print("\n⚠️  IMPORTANT: Make sure all 5 nodes are running!")
    print("   Start them in separate terminals with:")
    print("   python3 node.py 1")
    print("   python3 node.py 2")
    print("   python3 node.py 3")
    print("   python3 node.py 4")
    print("   python3 node.py 5")
    print("\n   Or use: ./start_nodes.sh")
    print("\n   Clean state first: ./clean_state.sh")
    print("\nThis script will guide you through each test.")
    print("You'll need to manually type commands in each node's terminal.")
    print("\nPress Enter to continue or Ctrl+C to exit...")
    try:
        input()
    except KeyboardInterrupt:
        print("\nExiting...")
        return
    
    tests = {
        "1": ("Sequential Transfers", runner.test_sequential_transfers),
        "2": ("Concurrent Transfers", runner.test_concurrent_transfers),
        "3": ("Insufficient Funds", runner.test_insufficient_funds),
        "4": ("Node Failure", runner.test_node_failure),
        "5": ("Leader Failure", runner.test_leader_failure),
        "6": ("Multiple Node Failures", runner.test_multiple_node_failure),
        "7": ("Network Partition (Minority vs Majority)", runner.test_partition),
    }
    
    print("\nAvailable tests:")
    for key, (name, _) in tests.items():
        print(f"  {key}. {name}")
    print("  all. Run all tests")
    print("  clean. Clean state files")
    
    choice = input("\nSelect test (1-7, all, or clean): ").strip().lower()
    
    if choice == "clean":
        runner.cleanup_state()
    elif choice == "all":
        for name, test_func in tests.values():
            try:
                test_func()
                print("\nPress Enter to continue to next test...")
                input()
            except KeyboardInterrupt:
                print("\n\nTest interrupted. Exiting...")
                break
    elif choice in tests:
        name, test_func = tests[choice]
        try:
            test_func()
        except KeyboardInterrupt:
            print("\n\nTest interrupted.")
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()

