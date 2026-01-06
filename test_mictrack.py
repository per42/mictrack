from unittest import TestCase
from unittest.mock import Mock

from mictrack import *


def check_issue_command(data: dict, tx: bytes, rx: bytes):
    command: Command = TypeAdapter(AnyCommand).validate_python(data)

    io = Mock(RawIOBase)
    io.write.side_effect = lambda b: len(b)
    io.read.return_value = rx

    try:
        issue_command(io, command)
    except Exception as e:
        e.add_note(repr(command))
        raise

    io.write.assert_called_once_with(tx)
    io.read.assert_called_once_with(MORE_THAN_CAN_BE_READ)


class TestMictrack(TestCase):
    def test_issue_command(self):
        for command, tx, rx in [
            (
                {
                    "command": "START",
                },
                b"ETS",
                b"ETS,OK",
            ),
            (
                {
                    "command": "PASSWORD",
                    "password": "aB35",
                },
                b"777,aB35",
                b"777,OK",
            ),
            (
                {
                    "command": "ACCESS_POINT",
                    "apn": "iot.1nce.net",
                    "username": "",
                    "password": "",
                },
                b"803,iot.1nce.net,,",
                b"803,OK",
            ),
            (
                {
                    "command": "SERVER",
                    "host": "demo.traccar.org",
                    "port": 5030,
                },
                b"804,demo.traccar.org,5030",
                b"804,OK",
            ),
            (
                {
                    "command": "MODE",
                    "mode": "AUTO",
                    "interval_vibration": 10,
                    "interval_still": 1,
                },
                b"MODE,0,10,1",
                b"MODE,OK",
            ),
            (
                {
                    "command": "MODE",
                    "mode": "REAL_TIME",
                    "interval": 30,
                },
                b"MODE,1,30",
                b"MODE,OK",
            ),
            (
                {
                    "command": "MODE",
                    "mode": "GNSS_AUTO",
                    "interval": 10,
                    "gnss_always_on": True,
                    "tcp_always_on": False,
                },
                b"MODE,2,10,1,0",
                b"MODE,OK",
            ),
            (
                {
                    "command": "MODE",
                    "mode": "HOME",
                    "interval": 10,
                },
                b"MODE,8,10",
                b"MODE,OK",
            ),
            (
                {
                    "command": "LOCK",
                    "interval": 10,
                    "duration": 1,
                },
                b"LOCK,10,1",
                b"LOCK,OK",
            ),
            (
                {
                    "command": "PROTOCOL",
                    "protocol": "TCP",
                },
                b"800,TCP",
                b"800,OK",
            ),
            (
                {
                    "command": "LOCATE",
                },
                b"WHERE",
                b"",
            ),
            (
                {
                    "command": "HEARTBEAT",
                    "interval": 5,
                },
                b"HBC,5",
                b"HBC,OK",
            ),
            (
                {
                    "command": "GNSS",
                    "duration": 5,
                },
                b"DUR,5",
                b"DUR,OK",
            ),
            (
                {
                    "command": "LAST_KNOWN_POSITION",
                    "enabled": True,
                },
                b"LEP,1",
                b"LEP,ON",
            ),
            (
                {
                    "command": "LAST_KNOWN_POSITION",
                    "enabled": False,
                },
                b"LEP,0",
                b"LEP,OFF",
            ),
            (
                {
                    "command": "LOCATION_BASED_SERVICES",
                    "mode": "WIFI_FALLBACK",
                },
                b"LBS,1",
                b"LBS,OK",
            ),
            (
                {
                    "command": "WIFI",
                    "enabled": True,
                },
                b"AGPS,1",
                b"AGPS,ON",
            ),
            (
                {
                    "command": "BUTTON",
                    "enabled": False,
                },
                b"MSW,0",
                b"MSW,OFF",
            ),
            (
                {
                    "command": "TIME_ZONE",
                    "timezone": 8.0,
                },
                b"896,+480",
                b"896,OK",
            ),
            (
                {
                    "command": "KEEP_ALIVE",
                    "duration": 60,
                },
                b"RWT,60",
                b"RWT,OK",
            ),
            (
                {
                    "command": "POSITIONING",
                    "priority": "WIFI",
                },
                b"PRIOR,1",
                b"PRIOR,WIFI",
            ),
            (
                {
                    "command": "WIRELESS",
                    "technology": "LTE",
                    "lte_cat": "M1",
                    "priority": "LTE_M1",
                },
                b"NWM,3,0,2",
                b"NWM,OK",
            ),
            (
                {
                    "command": "WIRELESS",
                    "technology": "LTE",
                    "lte_cat": "NB1",
                    "priority": "LTE_NB1",
                },
                b"NWM,3,1,3",
                b"NWM,OK",
            ),
            (
                {
                    "command": "WIRELESS",
                    "technology": "GSM",
                    "lte_cat": "ANY",
                    "priority": "GSM",
                },
                b"NWM,1,2,1",
                b"NWM,OK",
            ),
            (
                {
                    "command": "RADIO_BAND",
                    "lte_m1": "B12",
                    "lte_nb1": "ANY",
                },
                b"BAND,12,0,f",
                b"BAND,OK",
            ),
            (
                {
                    "command": "RADIO_BAND",
                    "lte_m1": "ANY",
                    "lte_nb1": "B20",
                },
                b"BAND,0,20,f",
                b"BAND,OK",
            ),
            (
                {
                    "command": "RADIO_BAND",
                    "lte_m1": "ANY",
                    "lte_nb1": "ANY",
                },
                b"BAND,0,0,f",
                b"BAND,OK",
            ),
            (
                {
                    "command": "SAVE_REBOOT",
                },
                b"REBOOT",
                b"REBOOT,OK",
            ),
            (
                {
                    "command": "RESET",
                },
                b"RESET",
                b"RESET,OK",
            ),
            (
                {
                    "command": "READ_CONF",
                },
                b"RCONF",
                b"\r\n<CFG>:NET:...",
            ),
            (
                {
                    "command": "SAVE_EXIT",
                },
                b"QTS",
                b"QTS,OK",
            ),
        ]:
            check_issue_command(
                command,
                tx,
                rx,
            )
