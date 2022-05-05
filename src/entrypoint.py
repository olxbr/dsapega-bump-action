import argparse
import json


def main():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("-c", "--config", help="Action configs", default="")
    args = parser.parse_args()
    cfg = args.config
    print("--------------------------------")
    print(cfg[1:])
    print("--------------------------------")
    print(cfg[:1])
    print("--------------------------------")
    print(f"O valor de teste é {json.loads(cfg)['test']}")


if __name__ == '__main__':
    main()
