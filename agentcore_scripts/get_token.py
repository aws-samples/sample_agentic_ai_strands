from utils import get_user_token
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--client', type=str)
    args = parser.parse_args()
    client_id = args.client
    print("Get token from client id")
    get_user_token(client_id)