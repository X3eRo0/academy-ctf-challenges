from __future__ import annotations

import contextlib
import dataclasses
import random
import string
import time
import re
from typing import Optional, Tuple, List

from pwn import remote, context
import logging

context.log_level = "critical"
logging.getLogger("pwnlib").setLevel(logging.CRITICAL)

__all__ = [
    "ServiceClient",
    "end_to_end_place",
    "retrieve_flag",
    "basic_havoc",
]


def _rand_str(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(random.choice(alphabet) for _ in range(length))


@dataclasses.dataclass
class Listing:
    id: int
    fid: int
    price: int
    sales: int
    note: str


class ServiceClient:
    def __init__(self, host: str, port: int, timeout: float = 5.0):
        # pwntools respects timeout on recv*
        self.host = host
        self.port = port
        self.timeout = timeout
        self.conn = None

    def connect(self) -> None:
        self.conn = remote(self.host, self.port, typ="tcp")
        self.conn.recvuntil(b"\n> ")

    def close(self) -> None:
        with contextlib.suppress(Exception):
            if self.conn is not None:
                self.conn.close()

    # --- helpers ---
    def _sendline(self, data: str) -> None:
        assert self.conn is not None
        self.conn.sendline(data.encode())

    def _recv_until_prompt(self) -> bytes:
        assert self.conn is not None
        return self.conn.recvuntil(b"\n> ")

    # --- protocol actions ---
    def register(self, username: str, password: str) -> str:
        self._sendline(f"register {username} {password}")
        out = self._recv_until_prompt().decode(errors="ignore")
        if "Registered user" not in out and "Username already exists" not in out:
            raise RuntimeError("register failed")
        return out

    def login(self, username: str, password: str) -> None:
        self._sendline(f"login {username} {password}")
        out = self._recv_until_prompt().decode(errors="ignore")
        if "Logged in as" not in out:
            raise RuntimeError("login failed")

    def whoami(self) -> str:
        self._sendline("whoami")
        out = self._recv_until_prompt().decode(errors="ignore")
        return out

    def parse_whoami(self) -> Tuple[str, int, int]:
        out = self.whoami()
        # Format: "<name> uid=<uid> balance=<balance>" or "Not logged in"
        if "Not logged in" in out:
            raise RuntimeError("not logged in")
        line = next((l for l in out.splitlines() if "uid=" in l and "balance=" in l), "")
        name = line.split()[0]
        m_uid = re.search(r"uid=(\d+)", line)
        m_bal = re.search(r"balance=(\d+)", line)
        if not m_uid or not m_bal:
            raise RuntimeError("whoami parse error")
        return name, int(m_uid.group(1)), int(m_bal.group(1))

    def balance(self) -> int:
        self._sendline("balance")
        out = self._recv_until_prompt().decode(errors="ignore")
        # Expected: "Balance: <num>"
        for line in out.splitlines():
            if line.startswith("Balance:"):
                return int(line.split(":", 1)[1].strip())
        raise RuntimeError("balance parse error")

    def deposit_flag(self, secret: str) -> int:
        self._sendline(f"deposit-flag {secret}")
        out = self._recv_until_prompt().decode(errors="ignore")
        # Expected: "Stored flag id=<id>"
        flag_id: Optional[int] = None
        for token in out.replace("\n", " ").split():
            if token.startswith("id="):
                try:
                    flag_id = int(token.split("=", 1)[1])
                except Exception:
                    pass
        if flag_id is None:
            raise RuntimeError("deposit-flag failed")
        return flag_id

    def my_flags(self) -> list[Tuple[int, str]]:
        self._sendline("my-flags")
        out = self._recv_until_prompt().decode(errors="ignore")
        flags: list[Tuple[int, str]] = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("id=") or line.startswith("Your flags:"):
                # format: "  id=<id> secret=<secret>"
                if line.startswith("Your flags:"):
                    continue
                parts = line.replace(",", " ").split()
                fid = None
                sec = None
                for p in parts:
                    if p.startswith("id="):
                        fid = int(p.split("=", 1)[1])
                    elif p.startswith("secret="):
                        sec = p.split("=", 1)[1]
                if fid is not None and sec is not None:
                    flags.append((fid, sec))
        return flags

    def list_flag(self, fid: int, price: int, note: str) -> int:
        # note might contain spaces; service uses %255[^\n]
        self._sendline(f"list-flag {fid} {price} {note}")
        out = self._recv_until_prompt().decode(errors="ignore")
        # Expected: "Created listing id=<id> price=<price>"
        lid: Optional[int] = None
        for token in out.replace("\n", " ").split():
            if token.startswith("id="):
                try:
                    lid = int(token.split("=", 1)[1])
                except Exception:
                    pass
        if lid is None:
            raise RuntimeError("list-flag failed")
        return lid

    def my_listings(self) -> list[Listing]:
        self._sendline("my-listings")
        out = self._recv_until_prompt().decode(errors="ignore")
        res: list[Listing] = []
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("id="):
                # "id=%llu fid=%llu price=%llu sales=%llu note=%s"
                # Parse simple tokens
                parts = line.split()
                vals = {}
                for p in parts:
                    if "=" in p:
                        k, v = p.split("=", 1)
                        vals[k] = v
                try:
                    res.append(
                        Listing(
                            id=int(vals.get("id", "0")),
                            fid=int(vals.get("fid", "0")),
                            price=int(vals.get("price", "0")),
                            sales=int(vals.get("sales", "0")),
                            note=vals.get("note", ""),
                        )
                    )
                except Exception:
                    pass
        return res

    def view_listing(self, lid: int) -> Optional[Listing]:
        self._sendline(f"view-listing {lid}")
        out = self._recv_until_prompt().decode(errors="ignore")
        if "Listing not found" in out:
            return None
        # "Listing id=%llu fid=%llu price=%llu sales=%llu note=%s"
        line = next((l for l in out.splitlines() if l.startswith("Listing ")), "")
        vals = {}
        for p in line.replace("Listing ", "").split():
            if "=" in p:
                k, v = p.split("=", 1)
                vals[k] = v
        try:
            return Listing(
                id=int(vals.get("id", "0")),
                fid=int(vals.get("fid", "0")),
                price=int(vals.get("price", "0")),
                sales=int(vals.get("sales", "0")),
                note=vals.get("note", ""),
            )
        except Exception:
            raise RuntimeError("view-listing parse error")

    def buy(self, lid: int) -> Tuple[int, str]:
        # On success, the service prints: "Purchased listing. New flag id=%lu secret=%s\n"
        self._sendline(f"buy {lid}")
        out = self._recv_until_prompt().decode(errors="ignore")
        if "Purchased listing." not in out:
            raise RuntimeError("buy failed")
        new_id: Optional[int] = None
        secret: Optional[str] = None
        for token in out.replace("\n", " ").split():
            if token.startswith("id="):
                try:
                    new_id = int(token.split("=", 1)[1])
                except Exception:
                    pass
            if token.startswith("secret="):
                secret = token.split("=", 1)[1]
        if new_id is None or secret is None:
            raise RuntimeError("buy parse error")
        return new_id, secret

    def delete_user(self) -> None:
        self._sendline("delete-user")
        _ = self._recv_until_prompt()

    def delete_flag(self, fid: int) -> None:
        self._sendline(f"delete-flag {fid}")
        _ = self._recv_until_prompt()

    def delete_listing(self, lid: int) -> None:
        self._sendline(f"delete-listing {lid}")
        _ = self._recv_until_prompt()

    def logout(self) -> None:
        self._sendline("logout")
        _ = self._recv_until_prompt()

    def register_and_login(self, username: str, password: str) -> None:
        self.register(username, password)
        self.login(username, password)


def end_to_end_place(client: ServiceClient, flag: str) -> Tuple[str, str]:
    # Returns (username, secret_flag) and leaves listing in place priced high.
    username = _rand_str(10)
    password = _rand_str(16)
    client.register(username, password)
    client.login(username, password)
    # sanity
    bal = client.balance()
    if bal < 0:
        raise RuntimeError("invalid balance")
    # deposit flag and list at high price
    fid = client.deposit_flag(flag)
    lid = client.list_flag(fid, 300000, note=_rand_str(10))
    # Verify listing shows up and links to our flag id
    listing = client.view_listing(lid)
    if listing is None or listing.fid != fid or listing.price != 300000:
        raise RuntimeError("listing verification failed")
    return str(lid), username, password 


def retrieve_flag(client: ServiceClient, username: str, password: str) -> str:
    client.login(username, password)
    flags = client.my_flags()
    if not flags:
        raise RuntimeError("no flags for user")
    # Our deposited flag should be the latest one; service orders by id
    return flags[-1][1]


def basic_havoc(client: ServiceClient) -> None:
    # A richer, randomized set of functionality checks
    scenarios: List[callable] = [
        lambda: _scenario_login_logout(client),
        lambda: _scenario_buy_flow(client),
        lambda: _scenario_delete_flow(client),
        lambda: _scenario_view_nonexistent(client),
    ]
    # Execute 2-3 random scenarios
    count = random.randint(2, 3)
    random.shuffle(scenarios)
    for fn in scenarios[:count]:
        fn()


def _scenario_login_logout(client: ServiceClient) -> None:
    
    username = _rand_str(6)
    password = _rand_str(12)
    client.register_and_login(username, password)
    name, uid, bal = client.parse_whoami()
    if name != username or bal < 0:
        raise RuntimeError("whoami mismatch")
    b = client.balance()
    if b != bal:
        raise RuntimeError("balance mismatch")
    client.logout()
    # login again
    client.login(username, password)
    client.logout()


def _scenario_buy_flow(client: ServiceClient) -> None:
    
    # Seller creates affordable listing; buyer purchases it
    seller = _rand_str(10)
    spw = _rand_str(12)
    buyer = _rand_str(10)
    bpw = _rand_str(12)

    # Create seller and list a flag
    client.register_and_login(seller, spw)
    secret = _rand_str(20)
    fid = client.deposit_flag(secret)
    price = random.randint(1, 80)  # affordable under initial 100 balance
    lid = client.list_flag(fid, price, note=_rand_str(10))
    listing = client.view_listing(lid)
    if listing is None or listing.fid != fid:
        raise RuntimeError("listing not visible")
    client.logout()

    # Buyer purchases
    client.register_and_login(buyer, bpw)
    new_id, bought_secret = client.buy(lid)
    if bought_secret != secret:
        raise RuntimeError("delivered secret mismatch")
    # Buyer should now have the new flag among my-flags
    flags = client.my_flags()
    if not any(fid2 == new_id and sec == secret for fid2, sec in flags):
        raise RuntimeError("newly bought flag not present")
    client.logout()

    # Seller sees sale_count incremented
    client.login(seller, spw)
    listing2 = client.view_listing(lid)
    if listing2 is None or listing2.sales < 1:
        raise RuntimeError("sale_count not incremented")
    client.logout()


def _scenario_delete_flow(client: ServiceClient) -> None:
    
    # Create flag and listing, verify deletion constraints, then cleanup
    username = _rand_str(6)
    password = _rand_str(12)
    client.register_and_login(username, password)
    secret = _rand_str(18)
    fid = client.deposit_flag(secret)
    lid = client.list_flag(fid, random.randint(50, 150), note="temp")
    # Try to delete flag while used by listing -> should still be present afterwards
    client.delete_flag(fid)
    flags = client.my_flags()
    if not any(f == fid for f, _ in flags):
        raise RuntimeError("flag unexpectedly deleted while listed")
    # Delete listing, then delete flag
    client.delete_listing(lid)
    client.delete_flag(fid)
    flags2 = client.my_flags()
    if any(f == fid for f, _ in flags2):
        raise RuntimeError("flag not deleted after listing removal")
    # Now deleting user should succeed
    client.delete_user()


def _scenario_view_nonexistent(client: ServiceClient) -> None:
    
    # Should gracefully handle unknown listing id
    bogus_id = random.randint(10_000, 50_000)
    listing = client.view_listing(bogus_id)
    if listing is not None:
        raise RuntimeError("unexpected listing exists")
    client.logout()
