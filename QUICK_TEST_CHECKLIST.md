# Quick Test Checklist

Use this as a quick reference while testing. See `TESTING_GUIDE.md` for detailed instructions.

## Setup (Before Each Test Session)

```bash
# 1. Clean state
./clean_state.sh

# 2. Start all nodes (5 terminals)
python3 node.py 1
python3 node.py 2
python3 node.py 3
python3 node.py 4
python3 node.py 5

# OR use the helper script (macOS only)
./start_nodes.sh
```

## Test Scenarios

### ✅ Test 1: Basic Sequential
- Node 1: `moneyTransfer 2 30`
- Wait ~25s
- Node 2: `moneyTransfer 3 20`
- Wait ~25s
- **Verify**: All nodes: `printBlockchain`, `printBalance` → Should match

### 🔥 Test 2: Concurrent (Multiple Leaders)
- **Quickly** send (within 1-2s):
  - Node 1: `moneyTransfer 2 10`
  - Node 3: `moneyTransfer 4 15`
  - Node 5: `moneyTransfer 1 20`
- Wait ~45s
- **Verify**: All nodes have 3 blocks, identical state

### ❌ Test 3: Insufficient Funds
- Node 1: `moneyTransfer 2 150` (only has $100)
- **Verify**: Error message, no block created

### 💥 Test 4: Non-Leader Failure
- Node 1: `moneyTransfer 2 30` → Wait ~25s
- Node 3: `failProcess`
- Node 2: `moneyTransfer 4 20` → Wait ~25s
- Node 3: `fixProcess` → Wait ~10s
- **Verify**: Node 3 synced, has 2 blocks

### 💥👑 Test 5: Leader Failure
- Node 1: `moneyTransfer 2 30`
- **Immediately**: Node 1: `failProcess` (within 1-2s)
- Wait ~30s (timeout)
- Node 2: `moneyTransfer 3 20` → Wait ~25s
- Node 1: `fixProcess` → Wait ~10s
- **Verify**: System made progress, Node 1 synced

### 💥💥 Test 6: Multiple Failures
- Node 4: `failProcess`
- Node 5: `failProcess`
- Node 1: `moneyTransfer 2 30` → Wait ~25s
- Node 2: `moneyTransfer 3 20` → Wait ~25s
- Node 4: `fixProcess`
- Node 5: `fixProcess` → Wait ~10s
- **Verify**: All nodes synced

## Verification Commands

After each test, run on **ALL nodes**:
```bash
printBlockchain
printBalance
```

## Quick Consistency Check

Run the automated checker:
```bash
python3 verify_consistency.py
```

## What to Look For

✅ **Good Signs:**
- All nodes have same blockchain length
- All nodes have identical blockchains
- All nodes have identical balances
- Total money = $500 (5 nodes × $100)
- Block hashes end in 0-4
- prev_hash links are correct

❌ **Bad Signs:**
- Different blockchain lengths
- Different balances
- Negative balances
- Blocks with invalid hashes
- Missing prev_hash links

## Common Issues

| Issue | Check |
|-------|-------|
| Nodes have different blockchains | Are decide messages being received? |
| Consensus stuck | Is majority calculation correct? (3/5) |
| Recovered node not syncing | Is state file being loaded? |
| Balance mismatches | Are blocks added in correct order? |

## Time Estimates

- Single transaction: ~25 seconds (consensus + network delay)
- Concurrent transactions: ~45 seconds (multiple rounds)
- Recovery sync: ~10 seconds

## Demo Preparation

Before your demo:
1. ✅ Test all scenarios above
2. ✅ Verify consistency checker passes
3. ✅ Practice the demo flow
4. ✅ Have clean state ready
5. ✅ Know your recovery mechanism

