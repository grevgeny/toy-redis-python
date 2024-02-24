import argparse
import asyncio
import logging

# main.py
from app.database import RedisDatabase
from app.redis_config import RedisConfig
from app.server import start_server


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    config = parse_args()
    db = RedisDatabase(config=config)

    host = "127.0.0.1"
    try:
        await start_server(host=host, port=config.port, db=db)
    finally:
        await db.close()


def parse_args() -> RedisConfig:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=6379, help="The port to listen on")
    parser.add_argument(
        "--replicaof",
        nargs=2,
        metavar=("MASTER_HOST", "MASTER_PORT"),
        default=[None, None],
        help="Master host and master port for the replica.",
    )
    parser.add_argument(
        "--dir", type=str, help="The directory where RDB files are stored"
    )
    parser.add_argument("--dbfilename", type=str, help="The name of the RDB file")

    args = parser.parse_args()

    return RedisConfig(
        port=args.port,
        rdb_dir=args.dir,
        rdb_filename=args.dbfilename,
        master_host=args.replicaof[0],
        master_port=args.replicaof[1],
        role="slave" if args.replicaof[0] else "master",
    )


if __name__ == "__main__":
    asyncio.run(main())
