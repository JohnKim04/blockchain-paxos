# Code Summary for Blockchain-Paxos Project

## Overview
This project implements a distributed blockchain system using Paxos consensus. The system consists of 5 nodes that maintain a replicated blockchain for money transfers. Each node can propose transactions, participate in consensus, and recover from failures.

---

## File 1: `blockchain.py`

### Purpose
Manages the blockchain data structure, block creation, validation, and persistence.

---

### Class: `Block`

Represents a single block in the blockchain containing one transaction.

#### `__init__(self, sender, receiver, amount, prev_hash, nonce=None)`
**Purpose**: Initialize a new block with transaction data.

**Parameters**:
- `sender`: Node ID sending money
- `receiver`: Node ID receiving money
- `amount`: Transfer amount
- `prev_hash`: Hash of previous block (creates chain linkage)
- `nonce`: Optional - if not provided, calculates one via Proof of Work

**How it's used**: Called when creating a new transaction block. Automatically calculates nonce if not provided.

---

#### `calculate_nonce(self)`
**Purpose**: Implements simplified Proof of Work (PoW). Finds a nonce such that `SHA256(transaction + nonce)` ends in 0-4.

**Algorithm**:
1. Generate random 8-character nonce
2. Compute hash of `sender + receiver + amount + nonce`
3. Check if last character is 0-4
4. Repeat until valid nonce found

**How it's used**: Called automatically during block creation. Ensures blocks require computational work, preventing trivial block creation.

**Example**: If hash is `abc123...4`, nonce is valid. If hash is `abc123...f`, try another nonce.

---

#### `compute_block_hash(self)`
**Purpose**: Computes the full block hash using the formula: `SHA256(transaction + nonce + prev_hash)`

**How it's used**: Creates the hash pointer that links blocks together. This hash becomes the `prev_hash` for the next block.

**Why important**: Ensures blockchain integrity - any modification to a block changes its hash, breaking the chain.

---

#### `to_dict(self)`
**Purpose**: Serializes block to dictionary for JSON storage/transmission.

**Returns**: Dictionary with all block fields (sender, receiver, amount, nonce, prev_hash, hash)

**How it's used**: When saving to disk or sending blocks over network (Paxos messages).

---

#### `from_dict(data)` (static method)
**Purpose**: Reconstructs a Block object from dictionary data.

**How it's used**: When loading blockchain from disk or receiving blocks from other nodes.

---

### Class: `Blockchain`

Manages the entire blockchain and account balances.

#### `__init__(self, node_id='0')`
**Purpose**: Initialize blockchain for a node.

**State**:
- `chain`: List of Block objects
- `balance_table`: Dictionary mapping node_id → balance
- Initializes all nodes (1-5) with $100 balance

**How it's used**: Created once per node at startup.

---

#### `initialize_balances(self)`
**Purpose**: Sets initial balance of $100 for all 5 nodes.

**How it's used**: Called during initialization. No blocks needed for initial money.

---

#### `get_balance(self, node_id)`
**Purpose**: Returns current balance for a node.

**How it's used**: Before creating transactions to check sufficient funds.

---

#### `create_block(self, receiver, amount)`
**Purpose**: Creates a new block for a money transfer. Does NOT add to chain yet (waits for Paxos consensus).

**Validation**:
- Checks sender has sufficient funds
- Gets previous block's hash (or "0"*64 for first block)
- Creates block with calculated nonce

**Returns**: Block object if valid, None if insufficient funds

**How it's used**: Called when user initiates `moneyTransfer` command. Block is then proposed via Paxos.

---

#### `add_block(self, block)`
**Purpose**: Validates and adds a block to the chain. This is called AFTER Paxos consensus is reached.

**Validation Steps**:
1. **Deduplication**: Check if block already exists (prevents duplicate DECIDE messages)
2. **Prev Hash**: Verify `block.prev_hash` matches current chain tip
3. **Proof of Work**: Verify nonce produces hash ending in 0-4
4. **Balance Check**: Verify sender had sufficient funds before this block

**If valid**:
- Appends block to chain
- Updates balance table (subtract from sender, add to receiver)
- Returns True

**If invalid**: Returns False, block rejected

**How it's used**: Called from `handle_paxos_decision()` when consensus is reached. This is the ONLY way blocks are added to the chain.

---

#### `save_to_disk(self)`
**Purpose**: Persists blockchain and balance table to JSON file.

**File format**: `state_node_{node_id}.json`

**How it's used**: 
- After each block is added
- Ensures state survives node crashes

---

#### `load_from_disk(self)`
**Purpose**: Loads blockchain and balance table from disk on startup or recovery.

**How it's used**: 
- Called during node initialization
- Called during recovery (`fixProcess` command)

---

## File 2: `node.py`

### Purpose
Implements the distributed node that handles networking, Paxos coordination, and user interface.

---

### Class: `Node`

Represents a single node in the distributed system.

#### `__init__(self, node_id)`
**Purpose**: Initialize a node with networking, blockchain, and Paxos components.

**Initialization Steps**:
1. Load configuration (IP, port for all nodes)
2. Create Blockchain instance and load from disk
3. Create PaxosInstance with callbacks
4. Set up TCP server socket
5. Start two threads:
   - `listen_thread`: Accepts incoming connections
   - `cli_thread`: Handles user commands

**How it's used**: Called once when starting a node: `python3 node.py 1`

---

#### `accept_connections(self)`
**Purpose**: Continuously listens for incoming TCP connections from other nodes.

**How it's used**: Runs in background thread. Spawns new thread for each connection to handle messages concurrently.

---

#### `handle_incoming_message(self, conn)`
**Purpose**: Processes a single incoming message from another node.

**Steps**:
1. If node is failed, drop connection immediately
2. Receive all data from connection
3. Parse JSON message
4. Route to appropriate handler via `process_message()`

**How it's used**: Called for each incoming connection. Handles all Paxos messages and sync requests.

---

#### `process_message(self, msg)`
**Purpose**: Routes incoming messages to appropriate handlers based on message type.

**Message Types**:
- `PREPARE`, `PROMISE`, `ACCEPT`, `ACCEPTED`, `DECIDE` → Paxos handlers
- `REQUEST_BLOCKCHAIN`, `BLOCKCHAIN_RESPONSE` → Sync handlers

**How it's used**: Central message router for all node-to-node communication.

---

#### `send_msg(self, target_id, message_str)`
**Purpose**: Sends a message string to a specific node via TCP.

**Features**:
- 3-second network delay (simulates real network)
- Checks if node is failed before sending
- Runs in separate thread (non-blocking)
- Handles connection errors gracefully

**How it's used**: Low-level message sending. Called by `send_msg_dict()` and `broadcast()`.

---

#### `send_msg_dict(self, target_id, msg_dict)`
**Purpose**: Helper to send dictionary as JSON string.

**How it's used**: Wrapper for sending structured messages (Paxos messages, sync requests).

---

#### `broadcast(self, msg_dict)`
**Purpose**: Sends message to all other nodes (peers).

**How it's used**: For Paxos PREPARE, ACCEPT, and DECIDE messages that need to reach all nodes.

---

#### `handle_paxos_decision(self, block_data)`
**Purpose**: Callback from Paxos when consensus is reached on a block.

**Steps**:
1. Convert block data to Block object
2. Add block to blockchain (validates and updates balances)
3. Save state to disk

**How it's used**: Called by Paxos when majority agrees on a block. This is where blocks are actually committed.

---

#### `sync_blockchain(self)`
**Purpose**: Requests blockchain from peers after node recovery.

**Steps**:
1. Broadcast REQUEST_BLOCKCHAIN to all peers
2. Wait 8 seconds for responses
3. Process all responses and pick longest valid chain
4. Update local blockchain

**How it's used**: Called during `fixProcess` command to sync with network after crash.

---

#### `handle_blockchain_request(self, msg)`
**Purpose**: Responds to blockchain sync request from recovering node.

**How it's used**: When another node requests our blockchain, we send our chain and balance table.

---

#### `handle_blockchain_response(self, msg)`
**Purpose**: Processes blockchain received from peer during sync.

**How it's used**: Stores response for batch processing, or processes immediately if not actively syncing.

---

#### `process_sync_responses(self)`
**Purpose**: After collecting sync responses, picks longest valid chain and updates.

**Algorithm**:
1. Find longest chain from all responses
2. Validate chain structure (prev_hash links, PoW)
3. Validate balances (replay transactions)
4. Update local blockchain if valid

**How it's used**: Called after waiting period during sync to process all responses together.

---

#### `validate_chain_structure(self, chain)`
**Purpose**: Quick validation of chain integrity (prev_hash links and PoW).

**How it's used**: Pre-validation before full chain validation during sync.

---

#### `validate_and_update_chain(self, new_chain, new_balance_table)`
**Purpose**: Full validation of received chain including balance replay.

**Validation**:
1. Check prev_hash links
2. Verify PoW for each block
3. Replay transactions to verify balances
4. If valid, replace local chain

**How it's used**: During sync to ensure received chain is valid before accepting.

---

#### `handle_cli(self)`
**Purpose**: Command-line interface for user interactions.

**Commands**:
- `moneyTransfer <dest> <amt>`: Initiate transaction
- `failProcess`: Simulate node crash
- `fixProcess`: Recover node and sync
- `printBlockchain`: Display blockchain
- `printBalance`: Display balances
- `exit`: Shutdown node

**How it's used**: Runs in background thread, processes user input continuously.

---

## File 3: `paxos.py`

### Purpose
Implements the Paxos consensus algorithm to ensure all nodes agree on the same blocks.

---

### Class: `PaxosInstance`

Manages Paxos state for reaching consensus on blockchain blocks.

#### `__init__(self, node_id, num_nodes, callback_broadcast, callback_send, callback_decide, get_blockchain_depth)`
**Purpose**: Initialize Paxos with node info and callbacks.

**State Variables**:
- **Proposer**: `seq_num`, `my_proposal_val`, `promises`, `accepts_received`, `is_leader`
- **Acceptor**: `max_ballot_promised`, `accepted_ballot`, `accepted_val`
- **Deduplication**: `decided_blocks` set

**How it's used**: Created once per node, handles all consensus operations.

---

#### `compare_ballots(self, b1, b2)`
**Purpose**: Compares two ballots to determine which is higher.

**Ballot Structure**: `[seq_num, node_id, depth]`

**Comparison Order**:
1. Depth (higher wins)
2. Sequence number (higher wins)
3. Node ID (higher wins)

**Returns**: 1 if b1 > b2, -1 if b1 < b2, 0 if equal

**How it's used**: Critical for Paxos safety - determines which proposals take precedence.

---

#### `prepare(self, block_val)`
**Purpose**: Phase 1a - Proposer sends PREPARE to start consensus.

**Steps**:
1. Store block to propose
2. Increment sequence number
3. Get current blockchain depth
4. Create ballot `[seq_num, node_id, depth]`
5. Broadcast PREPARE to all nodes
6. Handle locally (self-promise)
7. Start timeout timer

**How it's used**: Called when node wants to propose a transaction block. Initiates Paxos protocol.

---

#### `start_proposal_timer(self)`
**Purpose**: Starts 20-second timeout for proposal.

**How it's used**: If consensus not reached, triggers retry with higher sequence number.

---

#### `handle_timeout(self)`
**Purpose**: Called if consensus not reached within timeout.

**Behavior**:
- If node failed: Cancel retry
- Otherwise: Retry with higher sequence number

**How it's used**: Handles leader failures and network issues. Ensures liveness.

---

#### `cancel_proposal(self)`
**Purpose**: Cancels pending proposal when node fails.

**How it's used**: Called during `failProcess` to stop Paxos activity.

---

#### `handle_prepare(self, msg)`
**Purpose**: Phase 1b - Acceptor receives PREPARE.

**Logic**:
- If ballot > `max_ballot_promised`: Promise to this ballot
- Send PROMISE with any previously accepted value
- Otherwise: Ignore (lower ballot)

**How it's used**: All nodes act as acceptors. Ensures only higher ballots are accepted.

---

#### `handle_promise(self, msg)`
**Purpose**: Phase 2a - Proposer receives PROMISE.

**Steps**:
1. Store promise
2. Check if majority (≥ 3 out of 5) received
3. If majority: Become leader
4. Check if any acceptor already accepted a value
5. If yes: Use that value (safety property)
6. Otherwise: Use own proposal
7. Send ACCEPT to all nodes

**How it's used**: When proposer gets enough promises, it becomes leader and proposes value.

---

#### `handle_accept(self, msg)`
**Purpose**: Phase 2b - Acceptor receives ACCEPT.

**Logic**:
- If ballot ≥ `max_ballot_promised`: Accept the value
- Send ACCEPTED to leader
- Otherwise: Ignore

**How it's used**: Acceptors accept values from ballots they've promised to.

---

#### `handle_accepted(self, msg)`
**Purpose**: Phase 3 - Leader receives ACCEPTED.

**Steps**:
1. Track which nodes accepted
2. If majority accepted: Consensus reached!
3. Cancel timeout
4. Check for duplicates
5. Broadcast DECIDE to all nodes
6. Handle locally

**How it's used**: When majority accepts, consensus is achieved. Leader broadcasts decision.

---

#### `handle_decide(self, msg)`
**Purpose**: Phase 4 - Learner receives DECIDE.

**Steps**:
1. Check if already processed (deduplication)
2. Mark block as decided
3. Cancel timeout
4. Call `decide_callback()` to add block to blockchain
5. Reset state for next round

**How it's used**: All nodes learn the decided value and commit it to their blockchain.

---

## System Flow

### Transaction Flow:
1. User: `moneyTransfer 2 30` on Node 1
2. Node 1: `blockchain.create_block()` → Creates block
3. Node 1: `paxos.prepare(block)` → Starts Paxos
4. All nodes: Exchange PREPARE/PROMISE/ACCEPT/ACCEPTED messages
5. Leader: Gets majority → Broadcasts DECIDE
6. All nodes: `handle_decide()` → `handle_paxos_decision()` → `blockchain.add_block()`
7. All nodes: Block committed, balances updated

### Failure Recovery Flow:
1. Node crashes: `failProcess` → Sets `failed = True`, cancels proposals
2. Other nodes: Continue operating (need majority = 3)
3. Node recovers: `fixProcess` → Loads from disk, calls `sync_blockchain()`
4. Sync: Requests chains from peers, validates, updates to longest valid chain

---

## Key Design Decisions

1. **Ballot Structure**: `[seq_num, node_id, depth]` ensures one decision per blockchain position
2. **Deduplication**: `decided_blocks` set prevents processing same DECIDE twice
3. **Safety**: Leader adopts previously accepted values if found
4. **Persistence**: State saved to disk after each block commit
5. **Sync**: Recovered nodes request and validate chains from peers
6. **Network Delay**: 3-second delay simulates real network conditions

---

## Testing

The system handles:
- ✅ Sequential transactions
- ✅ Concurrent transactions (multiple leaders)
- ✅ Node failures (single and multiple)
- ✅ Leader failures during consensus
- ✅ Recovery and synchronization
- ✅ Insufficient funds validation

