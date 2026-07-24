# -*- coding: utf-8 -*-
"""SMTP account rotation for load balancing and quota management."""
from typing import List, Dict, Optional, Tuple
from .config import logger


class SMTPAccountRotator:
    """Rotuje między wieloma kontami SMTP."""

    def __init__(self, accounts: List[Dict[str, str]]):
        self.accounts = accounts
        self.current_index = 0
        self._usage_count: Dict[int, int] = {i: 0 for i in range(len(accounts))}
        self._max_per_account = 1000

    def set_max_per_account(self, max_per: int):
        self._max_per_account = max_per

    def next_account(self) -> Optional[Tuple[str, str, str, int]]:
        if not self.accounts:
            return None
        # Wybierz konto z najmniejszym użyciem
        # POPRAWKA: używamy range(len(self.accounts)) zamiast self.accounts.keys()
        sorted_idx = sorted(range(len(self.accounts)), key=lambda i: self._usage_count.get(i, 0))
        for idx in sorted_idx:
            if self._usage_count.get(idx, 0) < self._max_per_account:
                acc = self.accounts[idx]
                self.current_index = idx
                self._usage_count[idx] = self._usage_count.get(idx, 0) + 1
                return (acc.get("user", ""), acc.get("password", ""),
                        acc.get("host", "smtp-relay.gmail.com"),
                        int(acc.get("port", 587)))
        logger.warning("Wszystkie konta osiągnęły limit %d, resetuję użycie", self._max_per_account)
        self._usage_count = {i: 0 for i in range(len(self.accounts))}
        return self.next_account()

    def reset(self):
        self._usage_count = {i: 0 for i in range(len(self.accounts))}

    @classmethod
    def from_string(cls, data: str) -> "SMTPAccountRotator":
        accounts = []
        for line in data.strip().splitlines():
            if not line.strip():
                continue
            parts = line.strip().split(":")
            if len(parts) >= 4:
                accounts.append({
                    "user": parts[0],
                    "password": parts[1],
                    "host": parts[2],
                    "port": int(parts[3]),
                })
        return cls(accounts)