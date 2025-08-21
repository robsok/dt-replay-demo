import asyncio, argparse
from .config import load_config
from .publisher import run_publish

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-c", "--config", default="config/streams.yaml")
    args = ap.parse_args()
    cfg = load_config(args.config)
    try:
        asyncio.run(run_publish(cfg))
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()

