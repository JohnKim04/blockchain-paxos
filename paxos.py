import threading
import time
from utils import Logger

class PaxosInstance:
    """
    manager the paxos state for the current blockchain depth.
    """
    def __init__(self, node_id, num_nodes, callback_broadcast, callback_send, callback_decide, get_blockchain_depth):
        self.node_id = int(node_id)
        self.num_nodes = num_nodes
        self.broadcast = callback_broadcast
        self.send = callback_send
        self.decide_callback = callback_decide
        self.get_depth = get_blockchain_depth

        # proposer state
        self.seq_num = 0
        self.my_proposal_val = None # the block I want to propose
        self.promises = {} # node_id -> (accepted_ballot, accepted_val)
        self.accepts_received = set() # set of node_ids that accepted my proposal
        self.is_leader = False
        
        # acceptor state
        self.max_ballot_promised = (-1, -1, -1) 
        self.accepted_ballot = (-1, -1, -1)
        self.accepted_val = None
        
        self.proposal_timer = None
        
        # track decided blocks to prevent dup processing
        self.decided_blocks = set()  # Set of block hashes that have been decided
        # track if curr ballot has alr been decided/logged
        self.current_ballot_decided = None

    def compare_ballots(self, b1, b2):
        """
        Compare two ballots

        ballot structure: [seq_num, node_id, depth]
        comparison logic: Depth first, then seq_num, then node_id.
        returns: 1 if b1 > b2, -1 if b1 < b2, 0 if equal.
        """
        # b1: [seq1, id1, depth1]
        # b2: [seq2, id2, depth2]
        if b1[2] != b2[2]:
            return 1 if b1[2] > b2[2] else -1
        if b1[0] != b2[0]:
            return 1 if b1[0] > b2[0] else -1
        if b1[1] != b2[1]:
            return 1 if b1[1] > b2[1] else -1
        return 0

    def prepare(self, block_val):
        """
        step 1: proposer sends PREPARE.
        """
        self.my_proposal_val = block_val
        self.seq_num += 1
        current_depth = self.get_depth()
        
        ballot = [self.seq_num, self.node_id, current_depth]
        self.promises = {}
        self.is_leader = False
        
        Logger.log(self.node_id, f"[PAXOS] sending PREPARE ballot={ballot}")
        
        msg = {
            "type": "PREPARE",
            "sender": self.node_id,
            "ballot": ballot
        }
        self.broadcast(msg)
        self.handle_prepare(msg)
        
        self.start_proposal_timer()

    def start_proposal_timer(self):
        if self.proposal_timer:
            self.proposal_timer.cancel()
            
        # timeout > 2 * (max rtt + processing
        # delay is 3s one way. RTT ~ 6s. larger timeout -> 20 sec
        self.proposal_timer = threading.Timer(20.0, self.handle_timeout)
        self.proposal_timer.start()
        
    def handle_timeout(self):
        if not self.is_leader and self.my_proposal_val:
             if hasattr(self, 'is_node_active') and not self.is_node_active():
                 Logger.log(self.node_id, f"[PAXOS] Proposal Timeout, but node is failed. Cancelling retry.")
                 self.proposal_timer = None
                 return
             Logger.log(self.node_id, f"[PAXOS] Proposal Timeout. Restarting with higher seq_num.")
             self.prepare(self.my_proposal_val)
    
    def cancel_proposal(self):
        """Cancel any pending proposal timerl called when node fails."""
        if self.proposal_timer:
            self.proposal_timer.cancel()
            self.proposal_timer = None
            Logger.log(self.node_id, "[PAXOS] Cancelled pending proposal due to node failure.")
        self.my_proposal_val = None
        self.is_leader = False
        self.promises = {}
        self.accepts_received = set()

    def handle_prepare(self, msg):
        """
        step 2: acceptor receives PREPARE.
        """
        ballot = msg['ballot']
        sender = msg['sender']
        
        # if ballot > max_ballot_promised
        if self.compare_ballots(ballot, self.max_ballot_promised) > 0:
            self.max_ballot_promised = ballot
            
            Logger.log(self.node_id, f"[PAXOS] PROMISE to {sender} for ballot {ballot}")
            
            # send PROMISE
            response = {
                "type": "PROMISE",
                "sender": self.node_id,
                "ballot": ballot,
                "accepted_ballot": self.accepted_ballot,
                "accepted_val": self.accepted_val
            }
            self.send(sender, response)

    def handle_promise(self, msg):
        """
        step 3: Proposer receives PROMISE.
        """
        ballot = msg['ballot']
        sender = msg['sender']
        
        # check: if this promise corresponds to my current proposal ballot
        my_ballot = [self.seq_num, self.node_id, self.get_depth()]
        if self.compare_ballots(ballot, my_ballot) != 0:
            return

        self.promises[sender] = (msg['accepted_ballot'], msg['accepted_val'])
        
        # check for mjority
        if len(self.promises) >= (self.num_nodes // 2) + 1 and not self.is_leader:
            self.is_leader = True
            Logger.log(self.node_id, f"[PAXOS] Majority promises received. Becoming Leader.")
            
            highest_accepted_ballot = (-1, -1, -1)
            val_to_propose = self.my_proposal_val.to_dict()
            
            found_accepted_val = False
            for _, (acc_ballot, acc_val) in self.promises.items():
                if acc_val is not None:
                     if self.compare_ballots(acc_ballot, highest_accepted_ballot) > 0:
                         highest_accepted_ballot = acc_ballot
                         val_to_propose = acc_val
                         found_accepted_val = True
            
            if found_accepted_val:
                Logger.log(self.node_id, f"[PAXOS] Replacing proposal with already accepted value.")

            # Send ACCEPT
            accept_msg = {
                "type": "ACCEPT",
                "sender": self.node_id,
                "ballot": my_ballot,
                "val": val_to_propose
            }
            self.broadcast(accept_msg)
            self.handle_accept(accept_msg)
            
            self.accepts_received = set()

    def handle_accept(self, msg):
        """
        Step 4: acceptor receives ACCEPT.
        """
        ballot = msg['ballot']
        val = msg['val']
        sender = msg['sender']
        
        if self.compare_ballots(ballot, self.max_ballot_promised) >= 0:
            self.max_ballot_promised = ballot
            self.accepted_ballot = ballot
            self.accepted_val = val
            
            Logger.log(self.node_id, f"[PAXOS] ACCEPTED ballot {ballot} from {sender}")
            
            response = {
                "type": "ACCEPTED",
                "sender": self.node_id,
                "ballot": ballot,
                "val": val
            }
            self.send(sender, response)

    def handle_accepted(self, msg):
        """
        Step 5: Leader receives ACCEPTED.
        """
        ballot = msg['ballot']
        sender = msg['sender']
        
        my_ballot = [self.seq_num, self.node_id, self.get_depth()]
        if self.compare_ballots(ballot, my_ballot) != 0:
            return

        self.accepts_received.add(sender)
        
        if len(self.accepts_received) >= (self.num_nodes // 2) + 1:
            # Consensus is reached
            if self.proposal_timer:
                self.proposal_timer.cancel()
                self.proposal_timer = None
                
            # handle dup/ only decide once per ballot
            val_hash = msg['val']['hash'] if msg['val'] else None
            if val_hash and val_hash in self.decided_blocks:
                return
            ballot_tuple = tuple(ballot)
            if self.current_ballot_decided == ballot_tuple:
                return
            self.current_ballot_decided = ballot_tuple
            
            Logger.log(self.node_id, f"[PAXOS] Consensus reached on val: {val_hash if val_hash else 'None'}")
            
            decide_msg = {
                "type": "DECIDE",
                "sender": self.node_id,
                "val": msg['val']
            }
            self.broadcast(decide_msg)
            
            self.handle_decide(decide_msg)

            self.accepts_received = set()

    def handle_decide(self, msg):
        """
        Step 6: Learner receives DECIDE.
        """
        val = msg['val']
        if not val:
            return
        
        block_hash = val.get('hash')
        if block_hash and block_hash in self.decided_blocks:
            Logger.log(self.node_id, f"[PAXOS] DECIDE for block {block_hash[:16]}... already processed, ignoring duplicate")
            return
        
        Logger.log(self.node_id, f"[PAXOS] DECIDE received. Committing block.")
        
        if block_hash:
            self.decided_blocks.add(block_hash)
        
        if self.proposal_timer:
            self.proposal_timer.cancel()
            self.proposal_timer = None
            
        self.decide_callback(val)
        
        self.accepted_val = None
        self.accepted_ballot = (-1, -1, -1)

