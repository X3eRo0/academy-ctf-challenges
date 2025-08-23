from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Tuple

# Ensure local imports work when executed as a script
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from ctf_gameserver import checkerlib

from service_checks import ServiceClient, end_to_end_place, retrieve_flag, basic_havoc


DEFAULT_PORT = int(os.environ.get("ACADEMY_BANK_PORT", "6969"))


@dataclass
class TeamState:
    username: str | None = None
    password: str | None = None


class AcademyBankChecker(checkerlib.BaseChecker):
    def _connect(self) -> ServiceClient:
        port = self.port or DEFAULT_PORT
        client = ServiceClient(self.ip, port)
        client.connect()
        return client

    def place_flag(self, tick: int) -> Tuple[checkerlib.CheckResult, str]:
        flag = checkerlib.get_flag(tick)
        client = self._connect()
        try:
            username, password = end_to_end_place(client, flag)
            # Persist credentials for get_flag
            state = TeamState(username=username, password=password)
            checkerlib.set_flagid(username, str(tick))
            checkerlib.store_state("state", state.__dict__)
            return checkerlib.CheckResult.OK, username
        except Exception as e:
            return checkerlib.CheckResult.FAULTY, f"place failed: {e}"
        finally:
            client.close()

    def check_service(self) -> checkerlib.CheckResult:
        client = self._connect()
        try:
            basic_havoc(client)
            return checkerlib.CheckResult.OK
        except Exception:
            return checkerlib.CheckResult.FAULTY
        finally:
            client.close()

    def get_flag(self, tick: int) -> checkerlib.CheckResult:
        # Load credentials from state
        state_dict = checkerlib.load_state("state") or {}
        username = state_dict.get("username")
        password = state_dict.get("password")
        if not username or not password:
            return checkerlib.CheckResult.FLAG_NOT_FOUND
        client = self._connect()
        try:
            secret = retrieve_flag(client, username, password)
            flag = checkerlib.get_flag(tick)
            if secret != flag:
                return checkerlib.CheckResult.FLAG_NOT_FOUND
            return checkerlib.CheckResult.OK
        except Exception:
            return checkerlib.CheckResult.FLAG_NOT_FOUND
        finally:
            client.close()


if __name__ == "__main__":
    checkerlib.run_check(AcademyBankChecker)

