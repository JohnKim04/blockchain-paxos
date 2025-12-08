import json
import hashlib
import sys

def load_config(path='config.json'):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file '{path}' not found.")
        sys.exit(1)

class Logger:
    @staticmethod
    def log(node_id, message):
        print(f"[Node {node_id}] {message}")
        sys.stdout.flush()

def compute_hash(data):
    """
    SHA256 helper.
    data can be string or bytes.
    """
    if isinstance(data, str):
        data = data.encode('utf-8')
    return hashlib.sha256(data).hexdigest()

def verify_nonce(hash_str):
    """
    Checks if the last character is 0-4.
    """
    if not hash_str:
        return False
    last_char = hash_str[-1]
    return last_char in ['0', '1', '2', '3', '4']

