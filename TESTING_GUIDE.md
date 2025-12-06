# Blockchain-Paxos Testing Guide

This guide provides a systematic approach to test all scenarios and edge cases for your blockchain-paxos implementation.

## Prerequisites

1. **Clean State**: Before each test, clean up state files:
   ```bash
   rm -f state_node_*.json
   ```

2. **Start All Nodes**: Open 5 terminal windows and start each node:
   ```bash
   # Terminal 1
   python3 node.py 1
   
   # Terminal 2
   python3 node.py 2
   
   # Terminal 3
   python3 node.py 3
   
   # Terminal 4
   python3 node.py 4
   
   # Terminal 5
   python3 node.py 5
   ```

3. **Wait for Nodes to Initialize**: Wait 2-3 seconds after starting all nodes before sending commands.

---

## Test Scenarios

### Test 1: Basic Sequential Transfers ✅
**Purpose**: Verify basic functionality with no concurrency or failures.

**Steps**:
1. On Node 1: `moneyTransfer 2 30`
2. Wait for consensus (watch logs for "DECIDE" messages)
3. On Node 1: `printBalance` → Should show Node 1: $70, Node 2: $130
4. On Node 2: `printBalance` → Should match Node 1
5. On Node 2: `moneyTransfer 3 20`
6. Wait for consensus
7. On all nodes: `printBalance` → Should show Node 2: $110, Node 3: $120
8. On Node 1: `printBlockchain` → Should show 2 blocks

**Expected Results**:
- All nodes have identical blockchains
- All nodes have identical balance tables
- Blocks are properly linked (prev_hash matches previous block's hash)
- Nonces produce hashes ending in 0-4

**Verification Checklist**:
- [ ] All 5 nodes show same blockchain length
- [ ] All 5 nodes show same balances
- [ ] Block hashes end with 0-4
- [ ] prev_hash of block N matches hash of block N-1
- [ ] Genesis block has prev_hash = "0"*64

---

### Test 2: Concurrent Transfers (Multiple Leaders) 🔥
**Purpose**: Test Paxos when multiple nodes try to become leader simultaneously.

**Steps**:
1. **Quickly** send these commands (within 1-2 seconds):
   - Node 1: `moneyTransfer 2 10`
   - Node 3: `moneyTransfer 4 15`
   - Node 5: `moneyTransfer 1 20`
2. Wait 30-40 seconds for all consensus rounds to complete
3. Check all nodes: `printBlockchain` and `printBalance`

**Expected Results**:
- Only ONE transaction per depth should be committed
- All nodes agree on the same sequence of blocks
- Balances are consistent across all nodes
- No double-spending (balances should be valid)

**Verification Checklist**:
- [ ] All nodes have same blockchain length (should be 3 blocks)
- [ ] All nodes have identical blockchains
- [ ] All nodes have identical balances
- [ ] No node has negative balance
- [ ] Total money in system = $500 (5 nodes × $100)

---

### Test 3: Insufficient Funds ❌
**Purpose**: Verify nodes reject transactions when sender lacks funds.

**Steps**:
1. On Node 1: `moneyTransfer 2 150` (Node 1 only has $100)
2. Check Node 1 output → Should show "Transaction failed (insufficient funds?)"
3. Verify no block was created: `printBlockchain` → Should be empty
4. Verify balances unchanged: `printBalance` → All should be $100

**Expected Results**:
- Transaction is rejected before Paxos starts
- No block is created
- Balances remain unchanged

---

### Test 4: Single Node Failure (Non-Leader) 💥
**Purpose**: Test system behavior when a non-leader node crashes.

**Steps**:
1. On Node 1: `moneyTransfer 2 30`
2. Wait for consensus to complete
3. On Node 3: `failProcess` (crash a non-leader)
4. On Node 2: `moneyTransfer 4 20`
5. Wait for consensus (should still work with 4 nodes)
6. On Node 3: `fixProcess` (recover)
7. Wait 5 seconds
8. On Node 3: `printBlockchain` and `printBalance`

**Expected Results**:
- System continues with 4 nodes (majority = 3)
- Node 3 recovers and syncs blockchain
- Node 3's blockchain matches other nodes after recovery

**Verification Checklist**:
- [ ] Node 3's blockchain length matches other nodes after recovery
- [ ] Node 3's balances match other nodes after recovery
- [ ] Node 3 can participate in new transactions after recovery

---

### Test 5: Leader Failure During Consensus 💥👑
**Purpose**: Test Paxos when leader crashes mid-consensus.

**Steps**:
1. On Node 1: `moneyTransfer 2 30`
2. **Immediately** (within 1 second): On Node 1: `failProcess`
3. Wait 25-30 seconds (timeout period)
4. On Node 2: `moneyTransfer 3 20` (new leader should emerge)
5. Wait for consensus
6. On Node 1: `fixProcess`
7. Wait 5 seconds
8. On Node 1: `printBlockchain` and `printBalance`

**Expected Results**:
- First transaction may or may not commit (depends on timing)
- Second transaction should commit successfully
- Node 1 recovers and syncs

**Verification Checklist**:
- [ ] System makes progress even after leader failure
- [ ] Node 1 recovers correctly
- [ ] All nodes eventually have consistent state

---

### Test 6: Multiple Concurrent Failures 💥💥
**Purpose**: Test system with 2 nodes down (still has majority).

**Steps**:
1. On Node 4: `failProcess`
2. On Node 5: `failProcess`
3. On Node 1: `moneyTransfer 2 30`
4. Wait for consensus (should work with 3 nodes)
5. On Node 2: `moneyTransfer 3 20`
6. Wait for consensus
7. On Node 4: `fixProcess`
8. On Node 5: `fixProcess`
9. Wait 5 seconds
10. Check all nodes: `printBlockchain` and `printBalance`

**Expected Results**:
- System continues with 3 nodes (majority = 3)
- Failed nodes recover and sync
- All nodes eventually consistent

---

### Test 7: Failure During Recovery (Edge Case) 🔄
**Purpose**: Test recovery when blockchain has grown significantly.

**Steps**:
1. On Node 3: `failProcess`
2. On Node 1: `moneyTransfer 2 10`
3. On Node 2: `moneyTransfer 4 15`
4. On Node 4: `moneyTransfer 5 20`
5. On Node 5: `moneyTransfer 1 25`
6. Wait for all consensus to complete
7. On Node 3: `fixProcess`
8. Wait 10 seconds
9. On Node 3: `printBlockchain` and `printBalance`

**Expected Results**:
- Node 3 recovers and gets all 4 blocks
- Node 3's state matches other nodes

---

### Test 8: Stale Prepare Messages (Depth Check) 📏
**Purpose**: Verify nodes reject prepare messages for old depths.

**Steps**:
1. On Node 1: `moneyTransfer 2 30`
2. Wait for consensus
3. On Node 2: `moneyTransfer 3 20`
4. Wait for consensus
5. On Node 5: `failProcess` (before it receives decide)
6. Wait 5 seconds
7. On Node 5: `fixProcess`
8. On Node 5: `printBlockchain` → Should have 2 blocks
9. Manually verify Node 5 doesn't accept old prepare messages

**Expected Results**:
- Node 5 rejects any prepare messages for depth < 2
- Node 5 only accepts proposals for depth >= 2

---

### Test 9: Rapid Sequential Transactions ⚡
**Purpose**: Test system under rapid transaction load.

**Steps**:
1. Send these commands quickly in sequence:
   - Node 1: `moneyTransfer 2 5`
   - Wait 2 seconds
   - Node 2: `moneyTransfer 3 5`
   - Wait 2 seconds
   - Node 3: `moneyTransfer 4 5`
   - Wait 2 seconds
   - Node 4: `moneyTransfer 5 5`
   - Wait 2 seconds
   - Node 5: `moneyTransfer 1 5`
2. Wait 40 seconds for all to complete
3. Check all nodes: `printBlockchain` and `printBalance`

**Expected Results**:
- All 5 transactions commit in order
- All nodes have identical state
- Balances are correct

---

### Test 10: Network Partition Simulation (Extra Credit) 🌐
**Purpose**: Test recovery after network partition.

**Steps**:
1. On Node 1: `moneyTransfer 2 30`
2. Wait for consensus
3. On Node 1: `failProcess`
4. On Node 2: `failProcess`
5. On Node 3: `moneyTransfer 4 20` (should work with 3 nodes)
6. Wait for consensus
7. On Node 1: `fixProcess`
8. On Node 2: `fixProcess`
9. Wait 10 seconds
10. Check all nodes: `printBlockchain` and `printBalance`

**Expected Results**:
- Partitioned nodes recover and sync
- All nodes eventually consistent

---

## Automated Testing Scripts

Use the provided `test_runner.py` script to automate some of these tests.

## Manual Verification Commands

After each test, run these on ALL nodes to verify consistency:

```bash
# On each node terminal:
printBlockchain
printBalance
```

Compare outputs - they should be identical across all nodes.

## Common Issues to Watch For

1. **Inconsistent Blockchains**: If nodes have different blockchain lengths, check:
   - Are decide messages being received?
   - Is the failed flag preventing message processing?
   - Are depth checks working correctly?

2. **Balance Mismatches**: If balances differ:
   - Check if blocks are being added in correct order
   - Verify balance updates happen only after decide
   - Check for double-spending

3. **Stuck Consensus**: If consensus never completes:
   - Check timeout handling
   - Verify majority calculation (should be 3 out of 5)
   - Check if failed nodes are being counted

4. **Recovery Issues**: If recovered nodes don't sync:
   - Verify state files are being read correctly
   - Check if recovery triggers blockchain sync
   - Verify depth comparison logic

## Success Criteria

Your implementation passes if:
- ✅ All nodes maintain consistent blockchains
- ✅ System makes progress with majority of nodes alive
- ✅ Failed nodes recover and sync correctly
- ✅ Concurrent transactions are handled correctly
- ✅ No double-spending occurs
- ✅ Balances are always consistent
- ✅ Blocks have valid nonces (hash ends in 0-4)
- ✅ Blocks are properly linked (prev_hash matches)

