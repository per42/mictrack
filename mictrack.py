"""Configure [Mictrack MT710](https://www.mictrack.com/downloads/user-manual/4g-gps-tracker/MT710_User_Manual_V1.0.pdf) over USB

Implements [mictrack MT710 USB Commands List](https://www.mictrack.com/downloads/Commands-list/Mictrack_MT710_Commands_List.pdf).

It substitutes CoolTerm in the [MT710 USB Config Tool Tutorial (macOS Version)](https://help.mictrack.com/articles/mt710-usb-config-tool-tutorial-macos-version/).
"""

from abc import abstractmethod
from collections.abc import Buffer
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum, IntEnum
from io import BytesIO, RawIOBase
from typing import Annotated, BinaryIO, ClassVar, Literal, get_args
from pydantic import BaseModel, Field, ConfigDict, TypeAdapter
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from serial import Serial, SerialBase, serial_for_url
import yaml
import logging
from argparse import ArgumentParser, FileType


class ExclusiveModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Time(ExclusiveModel):
    """Time in UTC"""

    hours: Annotated[int, Field(ge=0, lt=24)]
    minutes: Annotated[int, Field(ge=0, lt=60)]

    def __str__(self):
        return f"{self.hours}:{self.minutes}"


Arg = str | int | bool | Time
AckArg = str | bool


class Command(ExclusiveModel):
    command: str
    key: ClassVar[str]
    has_ack: ClassVar[bool] = True

    def args(self) -> tuple[Arg, ...]:
        return ()

    def ack_arg(self) -> AckArg:
        return "OK"


class Start(Command):
    command: Literal["START"]
    key = "ETS"


class Password(Command):
    """Set a password that is used for SMS commands"""

    command: Literal["PASSWORD"]
    key = "777"
    password: Annotated[
        str,
        Field(
            pattern="^[a-zA-Z0-9]{4}$",
            description="4 digits or letters",
            examples=["0000"],
        ),
    ]

    def args(self) -> tuple[Arg, ...]:
        return (self.password,)


class AccessPoint(Command):
    """Set the cellular operator access point name (APN) and credentials for the installed SIM

    Mictrack's preinstalled SIM use APN iot.1nce.net and empty username and password.
    """

    command: Literal["ACCESS_POINT"]
    key = "803"
    apn: Annotated[
        str, Field(description="Access point name", examples=["iot.1nce.net"])
    ]
    username: str = ""
    password: str = ""

    def args(self) -> tuple[Arg, ...]:
        return self.apn, self.username, self.password


class Server(Command):
    """Set the [Mictrack Communication Protocol](https://www.mictrack.com/downloads/protocols/Mictrack_Communication_Protocol_For_MT710_V1.0.pdf) server

    [Traccar](https://www.traccar.org/) accepts this protocol as [LTL-H2](https://www.traccar.org/devices/) on port 5030
    """

    command: Literal["SERVER"]
    key = "804"
    host: Annotated[
        str,
        Field(
            description="Host domain name or IP address", examples=["demo.traccar.org"]
        ),
    ]
    port: Annotated[int, Field(ge=0, lt=0x10000, examples=[5030])]

    def args(self) -> tuple[Arg, ...]:
        return self.host, self.port


class Mode(Command):
    command: Literal["MODE"]
    key = "MODE"
    mode: str
    index: ClassVar[int]

    def args(self) -> tuple[Arg, ...]:
        return self.index, *self.mode_args()

    @abstractmethod
    def mode_args(self) -> tuple[Arg, ...]: ...


class AutoMode(Mode):
    """Switch to shorter interval when vibrations are detected"""

    mode: Literal["AUTO"]
    index = 0
    interval_vibration: Annotated[
        int,
        Field(
            ge=10,
            le=600,
            description="Wakeup interval when vibrating [seconds]",
            examples=[10],
        ),
    ]
    interval_still: Annotated[
        int,
        Field(
            ge=1, le=24, description="Wakeup interval when still [hours]", examples=[1]
        ),
    ]

    def mode_args(self) -> tuple[Arg, ...]:
        return self.interval_vibration, self.interval_still


report_interval_10_600_s = Annotated[
    int,
    Field(ge=10, le=600, description="Report interval [seconds]", examples=[10]),
]
report_interval_10_60_s = Annotated[
    int,
    Field(ge=10, le=60, description="Report interval [seconds]", examples=[10]),
]
report_interval_5_60_m = Annotated[
    int,
    Field(ge=5, le=60, description="Report interval [minutes]", examples=[5]),
]


class RealTimeMode(Mode):
    """GNSS and IP is always on"""

    mode: Literal["REAL_TIME"]
    index = 1
    interval: report_interval_10_600_s

    def mode_args(self) -> tuple[Arg, ...]:
        return (self.interval,)


class GnssAutoMode(Mode):
    """GNSS and TCP will sleep and resume at wakeup, unless always on"""

    mode: Literal["GNSS_AUTO"]
    index = 2
    interval: Annotated[
        int,
        Field(ge=10, le=60, description="Wakeup interval [minutes]", examples=[10]),
    ]
    gnss_always_on: Annotated[bool, Field(description="GNSS is always on")]
    tcp_always_on: Annotated[bool, Field(description="TCP is always on")]

    def mode_args(self) -> tuple[Arg, ...]:
        return self.interval, self.gnss_always_on, self.tcp_always_on


class DeepSleepMode(Mode):
    """Sleep and resume at wakeup"""

    mode: Literal["DEEP_SLEEP"]
    index = 3
    interval: Annotated[
        int,
        Field(ge=1, le=24, description="Wakeup interval [hours]", examples=[1]),
    ]

    def mode_args(self) -> tuple[Arg, ...]:
        return (self.interval,)


class VibrateMode(Mode):
    """Sleep until vibration is detected

    It will go to sleep again after 7 minutes
    """

    mode: Literal["VIBRATE"]
    index = 4
    interval: report_interval_10_600_s

    def mode_args(self) -> tuple[Arg, ...]:
        return (self.interval,)


class WiFiOnlyMode(Mode):
    """Use Wi-Fi positioning only (no GNSS)"""

    mode: Literal["WIFI_ONLY"]
    index = 5
    interval: Annotated[
        int,
        Field(ge=10, le=60, description="Wakeup interval [minutes]", examples=[10]),
    ]
    tcp_always_on: Annotated[bool, Field(description="TCP is always on")]

    def mode_args(self) -> tuple[Arg, ...]:
        return self.interval, 0, self.tcp_always_on


class SmsOnlyMode(Mode):
    """Only responds to SMS message "WHERE<password>" with a google maps link"""

    mode: Literal["SMS_ONLY"]
    index = 6

    def mode_args(self) -> tuple[Arg, ...]:
        return ()


class SmartModeMixin:
    interval_vibration: Annotated[
        int,
        Field(
            ge=10,
            le=1440,
            description="Wakeup interval when vibrating [minutes]",
            examples=[10],
        ),
    ]
    interval_still: Annotated[
        int,
        Field(
            ge=1, le=24, description="Wakeup interval when still [hours]", examples=[1]
        ),
    ]

    def mode_args(self) -> tuple[Arg, ...]:
        return self.interval_vibration, self.interval_still


class SmartMode(SmartModeMixin, Mode):
    """Switch to shorter interval when vibrations are detected"""

    mode: Literal["SMART"]
    index = 7


class HomeMode(Mode):
    """When indoors it will go to sleep, and when outdoors and in motion wake up

    This mode is highly recommended for pet tracking.

    This mode must be used in conjunction with the "DEF,R" server/SMS command.
    """

    mode: Literal["HOME"]
    index = 8
    interval: report_interval_10_600_s

    def mode_args(self) -> tuple[Arg, ...]:
        return (self.interval,)


class WiFiPriorityMode(SmartModeMixin, Mode):
    """Smart mode with Wi-Fi priority over GNSS"""

    mode: Literal["WIFI_PRIO"]
    index = 9


class ClockMode(Mode):
    """Wakeup and report at set time"""

    mode: Literal["CLOCK"]
    index = 10

    duration: Annotated[
        str,
        Field(
            ge=0,
            lt=24,
            description="Keep waking up for this duration [hours]. 0 means one per day",
        ),
    ]
    time: Time

    def args(self) -> tuple[Arg, ...]:
        return self.duration, self.time


class Lock(Command):
    """Lock to report interval for a duration"""

    command: Literal["LOCK"]
    key = "LOCK"

    interval: report_interval_10_60_s
    duration: Annotated[
        int,
        Field(
            ge=0,
            le=60,
            description="Locked duration before reverting to current mode [minutes]",
        ),
    ]

    def args(self) -> tuple[Arg, ...]:
        return self.interval, self.duration


class Protocol(Command):
    """IP Protocol for server"""

    command: Literal["PROTOCOL"]
    key = "800"

    protocol: Annotated[Literal["TCP", "UDP"], Field(examples=["TCP"])]

    def args(self) -> tuple[Arg, ...]:
        return (self.protocol,)


class Locate(Command):
    """Check GNSS Coordinates"""

    command: Literal["LOCATE"]
    key = "WHERE"
    has_ack = False


class Heartbeat(Command):
    """Heartbeat interval"""

    command: Literal["HEARTBEAT"]
    key = "HBC"

    interval: report_interval_5_60_m

    def args(self) -> tuple[Arg, ...]:
        return (self.interval,)


class Gnss(Command):
    """GNSS search duration after wakeup"""

    command: Literal["GNSS"]
    key = "DUR"

    duration: Annotated[
        int,
        Field(ge=1, le=10, description="duration [minutes]", examples=[2]),
    ]

    def args(self) -> tuple[Arg, ...]:
        return (self.duration,)


class EnabledMixin:
    enabled: bool

    def args(self) -> tuple[Arg, ...]:
        return (self.enabled,)

    def ack_arg(self) -> AckArg:
        return self.enabled


class LastKnownPosition(EnabledMixin, Command):
    """When GNSS is unavailable the last known position is reported"""

    command: Literal["LAST_KNOWN_POSITION"]
    key = "LEP"


LbsMode = Literal["DISABLED", "WIFI_FALLBACK", "WIFI_4MAC_FALLBACK", "GNSS_FALLBACK"]


class LocationBasedServices(Command):
    """How to use the cellular Location Based Services (LBS) as fallback"""

    command: Literal["LOCATION_BASED_SERVICES"]
    key = "LBS"
    mode: LbsMode

    def args(self) -> tuple[Arg, ...]:
        return (get_args(LbsMode).index(self.mode),)


class WiFi(EnabledMixin, Command):
    """When GNSS is unavailable the Wi-Fi MACs are reported"""

    command: Literal["WIFI"]
    key = "AGPS"


class Button(EnabledMixin, Command):
    """Power/SOS button is enabled"""

    command: Literal["BUTTON"]
    key = "MSW"


class TimeZone(Command):
    """Set the timezone used for the WHERE SMS response"""

    command: Literal["TIME_ZONE"]
    key = "896"
    timezone: Annotated[Decimal, Field(ge=-12, le=13, description="Hours ahead of UTC")]

    def args(self) -> tuple[Arg, ...]:
        return (f"{round(self.timezone * 60):+}",)


class SaveReboot(Command):
    """Save config and reboot"""

    command: Literal["SAVE_REBOOT"]
    key = "REBOOT"


class Reset(Command):
    """Reset config"""

    command: Literal["RESET"]
    key = "RESET"


class ReadConf(Command):
    command: Literal["READ_CONF"]
    key = "RCONF"
    has_ack = False


class SaveExit(Command):
    """Save config and exit configuration"""

    command: Literal["SAVE_EXIT"]
    key = "QTS"


type AnyMode = Annotated[
    AutoMode
    | RealTimeMode
    | GnssAutoMode
    | DeepSleepMode
    | VibrateMode
    | WiFiOnlyMode
    | SmsOnlyMode
    | SmartMode
    | HomeMode
    | WiFiPriorityMode
    | ClockMode,
    Field(discriminator="mode"),
]

type AnyCommand = Annotated[
    Start
    | Password
    | AccessPoint
    | Server
    | AnyMode
    | Lock
    | Protocol
    | Locate
    | Heartbeat
    | Gnss
    | LastKnownPosition
    | LocationBasedServices
    | WiFi
    | Button
    | TimeZone
    | SaveReboot
    | Reset
    | ReadConf
    | SaveExit,
    Field(discriminator="command"),
]


def format_arg(arg: Arg) -> str:
    match (arg):
        case bool():
            return "1" if arg else "0"
        case int() | Time():
            return str(arg)
        case str():
            return arg


def format_ack_arg(arg: AckArg) -> str:
    match (arg):
        case bool():
            return "ON" if arg else "OFF"
        case str():
            return arg


MORE_THAN_CAN_BE_READ = 1000


def issue_command(io: RawIOBase, command: Command) -> None:
    """Write config to device"""

    io.write(
        ",".join((command.key, *(format_arg(a) for a in command.args()))).encode(
            "ASCII"
        )
    )
    rx = io.read(MORE_THAN_CAN_BE_READ)
    if command.has_ack:
        rx_exp = f"{command.key},{format_ack_arg(command.ack_arg())}".encode("ASCII")
        if rx_exp not in rx:
            raise RuntimeError("Expected response not received", rx_exp, rx)


@dataclass
class LoggingIO(RawIOBase):
    io: RawIOBase
    logger: logging.Logger
    encoding: str | None = None

    def write(self, b: Buffer, /) -> int | None:
        self.logger.getChild("write").debug(
            bytes(b).decode(self.encoding) if self.encoding is not None else b
        )
        return self.io.write(b)

    def read(self, size: int = -1, /) -> bytes | None:
        b = self.io.read(size)
        self.logger.getChild("read").debug(
            b.decode(self.encoding) if self.encoding is not None else b
        )
        return b


def main() -> None:
    parser = ArgumentParser()
    cmd = parser.add_subparsers(dest="cmd")
    config_parser = cmd.add_parser("config")
    config_parser.add_argument("port")
    config_parser.add_argument("config", type=FileType("rt", encoding="utf-8"))
    schema_parser = cmd.add_parser("write-schema")
    schema_parser.add_argument("schema", type=FileType("wt", encoding="utf-8"))
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger("mictrack")

    config_model = TypeAdapter(list[AnyCommand])
    if args.cmd == "write-schema":
        yaml.dump(
            config_model.json_schema(),
            args.schema,
            sort_keys=False,
        )
        return

    config = config_model.validate_python(yaml.safe_load(args.config))

    io = LoggingIO(
        Serial(
            args.port,
            baudrate=961200,
            timeout=0.1,
        ),
        logger.getChild("ser"),
        "utf-8",
    )
    for command in config:
        logger.info(f"Issuing command {command}")
        issue_command(io, command)


if __name__ == "__main__":
    main()
