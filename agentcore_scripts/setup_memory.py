from utils import setup_memclient
import argparse

if __name__ == '__main__':
    memory_id = setup_memclient()
    with open(".env_setup", "a") as f:
        f.write(f"MEMORY_ID={memory_id}\n")
    print(f"MEMORY_ID={memory_id} config saved to .env_setup")