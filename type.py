from typing import TypedDict


class Config(TypedDict):
    token: str
    prefix: str
    auto: bool
    auto_channel: int
    logging: bool
    log_channel: int
