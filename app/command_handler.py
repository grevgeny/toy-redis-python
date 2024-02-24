from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.database import RedisDatabase
from app.resp.encoder import RESPEncoder


@dataclass
class Command(ABC):
    @abstractmethod
    async def execute(self) -> bytes:
        pass


@dataclass
class PingCommand(Command):
    async def execute(self) -> bytes:
        return RESPEncoder.encode_simple_string("PONG")


@dataclass
class EchoCommand(Command):
    args: list[str]

    async def execute(self) -> bytes:
        if not self.args:
            return b"-ERR wrong number of arguments for 'echo' command\r\n"

        return RESPEncoder.encode_bulk_string(" ".join(self.args))


@dataclass
class SetCommand(Command):
    database: RedisDatabase
    args: list[str]

    async def execute(self) -> bytes:
        if len(self.args) < 2:
            return b"-ERR wrong number of arguments for 'set' command\r\n"

        key, value = self.args[0], self.args[1]
        expiry_ms = int(self.args[3]) if len(self.args) > 3 else None

        await self.database.set(key, value, expiry_ms)

        return RESPEncoder.encode_simple_string("OK")


@dataclass
class GetCommand(Command):
    database: RedisDatabase
    args: list[str]

    async def execute(self) -> bytes:
        if len(self.args) != 1:
            return b"-ERR wrong number of arguments for 'get' command\r\n"

        key = self.args[0]
        value = await self.database.get(key)

        if value is None:
            return RESPEncoder.encode_null()

        return RESPEncoder.encode_bulk_string(value)


@dataclass
class DeleteCommand(Command):
    database: RedisDatabase
    args: list[str]

    async def execute(self) -> bytes:
        if not self.args:
            return b"-ERR wrong number of arguments for 'del' command\r\n"

        total_deleted = sum([await self.database.delete(key) for key in self.args])

        return RESPEncoder.encode_integer(total_deleted)


@dataclass
class ConfigCommand(Command):
    database: RedisDatabase
    args: list[str]

    async def execute(self) -> bytes:
        if not self.args:
            return b"-ERR wrong number of arguments for 'config get' command\r\n"
        if self.args[0] == "get":
            key = self.args[1]
            if key == "dir":
                value = self.database.config.rdb_dir
            elif key == "dbfilename":
                value = self.database.config.rdb_filename
            else:
                return b"-ERR unknown config key\r\n"

            if value:
                return RESPEncoder.encode_array(key, value)
            else:
                return RESPEncoder.encode_null()
        else:
            return b"-ERR wrong arguments for 'config' command\r\n"


@dataclass
class KeysCommand(Command):
    database: RedisDatabase
    arg: str

    async def execute(self) -> bytes:
        if self.arg != "*":
            return b"-ERR wrong argument for 'keys' command\r\n"

        keys = await self.database.keys()

        return RESPEncoder.encode_array(*keys)


@dataclass
class InfoCommand(Command):
    database: RedisDatabase
    args: list[str]

    async def execute(self) -> bytes:
        if not self.args or self.args[0] != "replication":
            return b"-ERR wrong arguments for 'info' command provided\r\n"

        role = "role:master" if not self.database.config.master_host else "role:slave"
        master_replid = f"master_replid:{self.database.config.master_replid}"
        master_repl_offset = (
            f"master_repl_offset:{self.database.config.master_repl_offset}"
        )

        response_parts = [role, master_replid, master_repl_offset]
        response = "\n".join(response_parts)

        return RESPEncoder.encode_bulk_string(response)


@dataclass
class ReplconfCommand(Command):
    async def execute(self) -> bytes:
        return RESPEncoder.encode_simple_string("OK")


@dataclass
class PsyncCommand(Command):
    database: RedisDatabase

    async def execute(self) -> bytes:
        return RESPEncoder.encode_simple_string(
            f"FULLRESYNC {self.database.config.master_replid} {self.database.config.master_repl_offset}"
        )


@dataclass
class CommandUnknown(Command):
    name: str

    async def execute(self) -> bytes:
        return f"-ERR unknown command {self.name}".encode()


async def create_command(raw_command: list[str], database: RedisDatabase) -> Command:
    match raw_command:
        case ["ping"]:
            return PingCommand()
        case ["echo", *args]:
            return EchoCommand(args=args)
        case ["set", *args]:
            return SetCommand(database=database, args=args)
        case ["get", *args]:
            return GetCommand(database=database, args=args)
        case ["del", *args]:
            return DeleteCommand(database=database, args=args)
        case ["config", *args]:
            return ConfigCommand(database=database, args=args)
        case ["keys", arg]:
            return KeysCommand(database=database, arg=arg)
        case ["info", *args]:
            return InfoCommand(database=database, args=args)
        case ["replconf", *args]:
            return ReplconfCommand()
        case ["psync", *args]:
            return PsyncCommand(database=database)
        case _:
            return CommandUnknown(name=raw_command[0])


class CommandHandler:
    def __init__(self, database: RedisDatabase) -> None:
        self.database = database

    async def handle_command(self, raw_command: list[str]) -> bytes:
        if not raw_command:
            return b"-ERR no command provided\r\n"

        command = await create_command(raw_command, self.database)
        return await command.execute()
