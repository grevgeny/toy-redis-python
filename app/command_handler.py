from app.config import RedisConfig
from app.database import RedisDatabase


class CommandHandler:
    def __init__(self, database: RedisDatabase, redis_config: RedisConfig) -> None:
        self.database = database
        self.redis_config = redis_config
        self.command_registry = {
            "ping": self.ping,
            "echo": self.echo,
            "set": self.set,
            "get": self.get,
            "del": self.delete,
            "config": self.config,
            "keys": self.keys,
        }

    async def handle_command(self, command: list[str]) -> bytes:
        """
        Dispatch the appropriate command to its handler and return the response.
        """
        if not command:
            return b"-ERR no command provided\r\n"

        cmd, *args = command[1:]

        handler = self.command_registry.get(cmd)
        if handler:
            return await handler(args)
        else:
            return f"-ERR unknown command '{cmd}'\r\n".encode()

    async def ping(self, args: list[str]) -> bytes:
        """
        Simple PING command.
        """
        return b"+PONG\r\n"

    async def echo(self, args: list[str]) -> bytes:
        """
        ECHO command to return the message sent to it.
        """
        if not args:
            return b"-ERR wrong number of arguments for 'echo' command\r\n"
        message = " ".join(args)
        return f"${len(message)}\r\n{message}\r\n".encode()

    async def set(self, args: list[str]) -> bytes:
        """
        SET command to store a value.
        """
        if len(args) < 2:
            return b"-ERR wrong number of arguments for 'set' command\r\n"
        key, value = args[0], args[1]
        expiry_ms = int(args[3]) if len(args) > 3 else None
        await self.database.set(key, value, expiry_ms)
        return b"+OK\r\n"

    async def get(self, args: list[str]) -> bytes:
        """
        GET command to retrieve a value.
        """
        if len(args) != 1:
            return b"-ERR wrong number of arguments for 'get' command\r\n"
        key = args[0]
        value = await self.database.get(key)
        if value is None:
            return b"$-1\r\n"
        return f"${len(value)}\r\n{value}\r\n".encode()

    async def delete(self, args: list[str]) -> bytes:
        """
        DEL command to delete one or more keys.
        """
        if not args:
            return b"-ERR wrong number of arguments for 'del' command\r\n"
        for key in args:
            await self.database.delete(key)
        return f":{len(args)}\r\n".encode()

    async def config(self, args: list[str]) -> bytes:
        if not args:
            return b"-ERR wrong number of arguments for 'config get' command\r\n"
        if args[0] == "get":
            key = args[1]
            if key == "dir":
                value = self.redis_config.dir
            elif key == "dbfilename":
                value = self.redis_config.dbfilename
            else:
                return b"-ERR unknown config key\r\n"
            return (
                f"*2\r\n${len(key)}\r\n{key}\r\n${len(value)}\r\n{value}\r\n".encode()
            )
        else:
            return b"-ERR wrong arguments for 'config' command\r\n"

    async def keys(self, args: list[str]) -> bytes:
        if not args:
            return b"-ERR wrong number of arguments for 'keys' command\r\n"
        if args[0] == "*":
            keys = await self.database.keys()
            n = len(keys)
            keys_array = [f"${len(key)}\r\n{key}\r\n" for key in keys]
        else:
            return b"-ERR wrong arguments for 'keys' command\r\n"
        return f"*{n}\r\n{''.join(keys_array)}".encode()