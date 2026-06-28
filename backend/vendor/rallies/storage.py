import json
import sqlite3
import threading
from pathlib import Path
from datetime import datetime, timezone

from .portfolio_names import DEFAULT_PORTFOLIO, normalize_portfolio_name
from .watchlist_names import DEFAULT_WATCHLIST, normalize_watchlist_name


class Storage:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = Path.home() / ".rallies" / "rallies.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._thread_conns = threading.local()
        self._init_db()

    def conn(self):
        if not hasattr(self._thread_conns, "conn") or self._thread_conns.conn is None:
            self._thread_conns.conn = sqlite3.connect(str(self.db_path))
            self._thread_conns.conn.row_factory = sqlite3.Row
            self._thread_conns.conn.execute("PRAGMA journal_mode=WAL")
            self._thread_conns.conn.execute("PRAGMA foreign_keys=ON")
        return self._thread_conns.conn

    def _init_db(self):
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    expires_at TEXT
                );
                CREATE TABLE IF NOT EXISTS watchlists (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS watchlist_tickers (
                    watchlist_name TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    added_at TEXT NOT NULL DEFAULT (datetime('now')),
                    notes TEXT DEFAULT '',
                    PRIMARY KEY (watchlist_name, ticker),
                    FOREIGN KEY (watchlist_name) REFERENCES watchlists(name) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS portfolios (
                    name TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS portfolio_positions (
                    portfolio_name TEXT NOT NULL,
                    ticker TEXT NOT NULL,
                    quantity REAL NOT NULL DEFAULT 0,
                    cost_basis REAL NOT NULL DEFAULT 0,
                    added_at TEXT NOT NULL DEFAULT (datetime('now')),
                    notes TEXT DEFAULT '',
                    PRIMARY KEY (portfolio_name, ticker),
                    FOREIGN KEY (portfolio_name) REFERENCES portfolios(name) ON DELETE CASCADE
                );
            """)
            conn.commit()
            self._migrate_legacy_watchlist_table(conn)
            self._migrate_legacy_portfolio_table(conn)
            self._dedupe_watchlist_tickers(conn)
            self._dedupe_portfolio_positions(conn)
        finally:
            conn.close()

    @staticmethod
    def _migrate_legacy_watchlist_table(conn) -> None:
        """Move legacy single watchlist table into watchlist_tickers."""
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='watchlist'"
        ).fetchone()
        if not row:
            return
        conn.execute(
            "INSERT OR IGNORE INTO watchlists (name) VALUES (?)",
            (DEFAULT_WATCHLIST,),
        )
        legacy = conn.execute(
            "SELECT ticker, added_at, notes FROM watchlist"
        ).fetchall()
        for r in legacy:
            ticker, added_at, notes = r[0], r[1], r[2]
            sym = str(ticker).upper().strip()
            if not sym or "/" in sym:
                continue
            conn.execute(
                "INSERT OR IGNORE INTO watchlist_tickers "
                "(watchlist_name, ticker, added_at, notes) VALUES (?, ?, ?, ?)",
                (DEFAULT_WATCHLIST, sym, added_at, notes or ""),
            )
        conn.execute("DROP TABLE watchlist")
        conn.commit()

    @staticmethod
    def _dedupe_watchlist_tickers(conn, watchlist_name: str | None = None) -> None:
        if watchlist_name:
            conn.execute(
                """
                DELETE FROM watchlist_tickers
                WHERE watchlist_name = ?
                AND rowid NOT IN (
                    SELECT MAX(rowid)
                    FROM watchlist_tickers
                    WHERE watchlist_name = ?
                    GROUP BY UPPER(TRIM(ticker))
                )
                """,
                (watchlist_name, watchlist_name),
            )
        else:
            conn.execute(
                """
                DELETE FROM watchlist_tickers
                WHERE rowid NOT IN (
                    SELECT MAX(rowid)
                    FROM watchlist_tickers
                    GROUP BY watchlist_name, UPPER(TRIM(ticker))
                )
                """
            )
        conn.commit()

    def _ensure_watchlist(self, watchlist_name: str) -> str:
        name = normalize_watchlist_name(watchlist_name)
        conn = self.conn()
        conn.execute(
            "INSERT OR IGNORE INTO watchlists (name) VALUES (?)",
            (name,),
        )
        conn.commit()
        return name

    @staticmethod
    def _migrate_legacy_portfolio_table(conn) -> None:
        """Move pre-named-portfolio `portfolio` table into portfolio_positions."""
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='portfolio'"
        ).fetchone()
        if not row:
            return
        conn.execute(
            "INSERT OR IGNORE INTO portfolios (name) VALUES (?)",
            (DEFAULT_PORTFOLIO,),
        )
        legacy = conn.execute(
            "SELECT ticker, quantity, cost_basis, added_at, notes FROM portfolio"
        ).fetchall()
        for r in legacy:
            ticker, quantity, cost_basis, added_at, notes = r[0], r[1], r[2], r[3], r[4]
            sym = str(ticker).upper().strip()
            conn.execute(
                "INSERT OR REPLACE INTO portfolio_positions "
                "(portfolio_name, ticker, quantity, cost_basis, added_at, notes) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    DEFAULT_PORTFOLIO,
                    sym,
                    float(quantity),
                    float(cost_basis),
                    added_at,
                    notes or "",
                ),
            )
        conn.execute("DROP TABLE portfolio")
        conn.commit()

    @staticmethod
    def _dedupe_portfolio_positions(conn, portfolio_name: str | None = None) -> None:
        """One row per (portfolio, ticker)."""
        if portfolio_name:
            conn.execute(
                """
                DELETE FROM portfolio_positions
                WHERE portfolio_name = ?
                AND rowid NOT IN (
                    SELECT MAX(rowid)
                    FROM portfolio_positions
                    WHERE portfolio_name = ?
                    GROUP BY UPPER(TRIM(ticker))
                )
                """,
                (portfolio_name, portfolio_name),
            )
        else:
            conn.execute(
                """
                DELETE FROM portfolio_positions
                WHERE rowid NOT IN (
                    SELECT MAX(rowid)
                    FROM portfolio_positions
                    GROUP BY portfolio_name, UPPER(TRIM(ticker))
                )
                """
            )
        conn.commit()

    def _ensure_portfolio(self, portfolio_name: str) -> str:
        name = normalize_portfolio_name(portfolio_name)
        conn = self.conn()
        conn.execute(
            "INSERT OR IGNORE INTO portfolios (name) VALUES (?)",
            (name,),
        )
        conn.commit()
        return name

    # --- Cache ---

    def cache_get(self, key):
        conn = self.conn()
        row = conn.execute(
            "SELECT value FROM cache WHERE key = ? AND (expires_at IS NULL OR expires_at > datetime('now'))",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return json.loads(row["value"])

    def cache_set(self, key, value, ttl_seconds=300):
        conn = self.conn()
        if ttl_seconds is None:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )
        else:
            conn.execute(
                "INSERT OR REPLACE INTO cache (key, value, expires_at) "
                "VALUES (?, ?, datetime('now', '+' || ? || ' seconds'))",
                (key, json.dumps(value), ttl_seconds),
            )
        conn.commit()

    def cache_delete(self, key):
        conn = self.conn()
        conn.execute("DELETE FROM cache WHERE key = ?", (key,))
        conn.commit()

    def cache_clear_expired(self):
        conn = self.conn()
        conn.execute("DELETE FROM cache WHERE expires_at IS NOT NULL AND expires_at <= datetime('now')")
        conn.commit()

    def cache_keys(self, prefix=None):
        conn = self.conn()
        if prefix:
            rows = conn.execute(
                "SELECT key FROM cache WHERE key LIKE ? AND (expires_at IS NULL OR expires_at > datetime('now'))",
                (f"{prefix}%",),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT key FROM cache WHERE expires_at IS NULL OR expires_at > datetime('now')"
            ).fetchall()
        return [row["key"] for row in rows]

    # --- Watchlist (named; default preserves legacy /watchlist behavior) ---

    def watchlist_add(self, ticker, notes="", *, watchlist_name: str = DEFAULT_WATCHLIST):
        wname = self._ensure_watchlist(watchlist_name)
        symbol = str(ticker).upper().strip()
        if not symbol or "/" in symbol:
            return False
        conn = self.conn()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT OR IGNORE INTO watchlist_tickers "
            "(watchlist_name, ticker, added_at, notes) VALUES (?, ?, ?, ?)",
            (wname, symbol, now, notes),
        )
        conn.commit()
        return conn.total_changes > 0

    def watchlist_remove(self, ticker, *, watchlist_name: str = DEFAULT_WATCHLIST):
        wname = normalize_watchlist_name(watchlist_name)
        conn = self.conn()
        conn.execute(
            "DELETE FROM watchlist_tickers WHERE watchlist_name = ? AND ticker = ?",
            (wname, str(ticker).upper().strip()),
        )
        conn.commit()
        return conn.total_changes > 0

    def watchlist_list(self, watchlist_name: str = DEFAULT_WATCHLIST):
        wname = normalize_watchlist_name(watchlist_name)
        conn = self.conn()
        self._dedupe_watchlist_tickers(conn, wname)
        rows = conn.execute(
            "SELECT ticker, added_at, notes FROM watchlist_tickers "
            "WHERE watchlist_name = ? ORDER BY added_at DESC, rowid DESC",
            (wname,),
        ).fetchall()
        return [
            {
                "watchlist_name": wname,
                "ticker": r["ticker"],
                "added_at": r["added_at"],
                "notes": r["notes"],
            }
            for r in rows
        ]

    def watchlist_list_names(self):
        conn = self.conn()
        rows = conn.execute(
            """
            SELECT w.name, w.created_at, COUNT(t.ticker) AS n_tickers
            FROM watchlists w
            LEFT JOIN watchlist_tickers t ON t.watchlist_name = w.name
            GROUP BY w.name
            ORDER BY w.name
            """
        ).fetchall()
        return [
            {
                "name": r["name"],
                "created_at": r["created_at"],
                "ticker_count": int(r["n_tickers"] or 0),
            }
            for r in rows
        ]

    def watchlist_create(self, watchlist_name: str) -> str:
        return self._ensure_watchlist(watchlist_name)

    def watchlist_delete(self, watchlist_name: str) -> bool:
        wname = normalize_watchlist_name(watchlist_name)
        if wname == DEFAULT_WATCHLIST:
            raise ValueError("Cannot delete the default watchlist; remove tickers instead.")
        conn = self.conn()
        conn.execute(
            "DELETE FROM watchlist_tickers WHERE watchlist_name = ?", (wname,)
        )
        conn.execute("DELETE FROM watchlists WHERE name = ?", (wname,))
        conn.commit()
        return conn.total_changes > 0

    def watchlist_rename(self, old_name: str, new_name: str) -> str:
        old = normalize_watchlist_name(old_name)
        new = self._ensure_watchlist(new_name)
        if old == new:
            return new
        if old == DEFAULT_WATCHLIST:
            raise ValueError("Cannot rename the default watchlist.")
        conn = self.conn()
        exists = conn.execute(
            "SELECT 1 FROM watchlists WHERE name = ?", (old,)
        ).fetchone()
        if not exists:
            raise ValueError(f"Watchlist '{old}' does not exist.")
        conn.execute("UPDATE watchlists SET name = ? WHERE name = ?", (new, old))
        conn.execute(
            "UPDATE watchlist_tickers SET watchlist_name = ? WHERE watchlist_name = ?",
            (new, old),
        )
        conn.commit()
        return new

    # --- Portfolio (named; default portfolio preserves legacy /portfolio behavior) ---

    def portfolio_add(
        self,
        ticker,
        quantity,
        cost_basis,
        notes="",
        *,
        portfolio_name: str = DEFAULT_PORTFOLIO,
    ):
        """Add or replace a position in a named portfolio (one row per ticker)."""
        pname = self._ensure_portfolio(portfolio_name)
        symbol = str(ticker).upper().strip()
        conn = self.conn()
        existing = conn.execute(
            "SELECT quantity, cost_basis FROM portfolio_positions "
            "WHERE portfolio_name = ? AND ticker = ?",
            (pname, symbol),
        ).fetchone()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "DELETE FROM portfolio_positions WHERE portfolio_name = ? AND ticker = ?",
            (pname, symbol),
        )
        conn.execute(
            "INSERT INTO portfolio_positions "
            "(portfolio_name, ticker, quantity, cost_basis, added_at, notes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pname, symbol, float(quantity), float(cost_basis), now, notes),
        )
        conn.commit()
        return {
            "portfolio_name": pname,
            "replaced": existing is not None,
            "previous": (
                {"quantity": existing["quantity"], "cost_basis": existing["cost_basis"]}
                if existing
                else None
            ),
        }

    def portfolio_remove(self, ticker, *, portfolio_name: str = DEFAULT_PORTFOLIO):
        pname = normalize_portfolio_name(portfolio_name)
        conn = self.conn()
        conn.execute(
            "DELETE FROM portfolio_positions WHERE portfolio_name = ? AND ticker = ?",
            (pname, str(ticker).upper().strip()),
        )
        conn.commit()
        return conn.total_changes > 0

    def portfolio_list(self, portfolio_name: str = DEFAULT_PORTFOLIO):
        pname = normalize_portfolio_name(portfolio_name)
        conn = self.conn()
        self._dedupe_portfolio_positions(conn, pname)
        rows = conn.execute(
            "SELECT ticker, quantity, cost_basis, added_at, notes FROM portfolio_positions "
            "WHERE portfolio_name = ? ORDER BY added_at DESC",
            (pname,),
        ).fetchall()
        return [
            {
                "portfolio_name": pname,
                "ticker": r["ticker"],
                "quantity": r["quantity"],
                "cost_basis": r["cost_basis"],
                "added_at": r["added_at"],
                "notes": r["notes"],
            }
            for r in rows
        ]

    def portfolio_get(self, ticker, *, portfolio_name: str = DEFAULT_PORTFOLIO):
        pname = normalize_portfolio_name(portfolio_name)
        conn = self.conn()
        row = conn.execute(
            "SELECT ticker, quantity, cost_basis FROM portfolio_positions "
            "WHERE portfolio_name = ? AND ticker = ?",
            (pname, str(ticker).upper().strip()),
        ).fetchone()
        if row is None:
            return None
        return {
            "portfolio_name": pname,
            "ticker": row["ticker"],
            "quantity": row["quantity"],
            "cost_basis": row["cost_basis"],
        }

    def portfolio_list_names(self):
        conn = self.conn()
        rows = conn.execute(
            """
            SELECT p.name, p.created_at, COUNT(pos.ticker) AS n_positions
            FROM portfolios p
            LEFT JOIN portfolio_positions pos ON pos.portfolio_name = p.name
            GROUP BY p.name
            ORDER BY p.name
            """
        ).fetchall()
        return [
            {
                "name": r["name"],
                "created_at": r["created_at"],
                "position_count": int(r["n_positions"] or 0),
            }
            for r in rows
        ]

    def portfolio_create(self, portfolio_name: str) -> str:
        return self._ensure_portfolio(portfolio_name)

    def portfolio_delete(self, portfolio_name: str) -> bool:
        pname = normalize_portfolio_name(portfolio_name)
        if pname == DEFAULT_PORTFOLIO:
            raise ValueError("Cannot delete the default portfolio; remove positions instead.")
        conn = self.conn()
        conn.execute(
            "DELETE FROM portfolio_positions WHERE portfolio_name = ?", (pname,)
        )
        conn.execute("DELETE FROM portfolios WHERE name = ?", (pname,))
        conn.commit()
        return conn.total_changes > 0

    def portfolio_rename(self, old_name: str, new_name: str) -> str:
        old = normalize_portfolio_name(old_name)
        new = self._ensure_portfolio(new_name)
        if old == new:
            return new
        conn = self.conn()
        if old == DEFAULT_PORTFOLIO:
            raise ValueError("Cannot rename the default portfolio.")
        exists = conn.execute(
            "SELECT 1 FROM portfolios WHERE name = ?", (old,)
        ).fetchone()
        if not exists:
            raise ValueError(f"Portfolio '{old}' does not exist.")
        conn.execute("UPDATE portfolios SET name = ? WHERE name = ?", (new, old))
        conn.execute(
            "UPDATE portfolio_positions SET portfolio_name = ? WHERE portfolio_name = ?",
            (new, old),
        )
        conn.commit()
        return new
