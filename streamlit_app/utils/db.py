"""
Database layer for CoHabitant application.

Phase 3 Upgrade: Connection pooling via @st.cache_resource.

Instead of opening a new TCP connection on every query (which exhausts SQL
Server connection limits under concurrency), this module now maintains a
singleton connection-pool factory cached for the lifetime of the Streamlit
server process. Connections are checked out, used, and returned — not
created and destroyed.

Architecture:
    @st.cache_resource  →  _init_connection_pool()  →  pyodbc pool reference
    get_db_connection()  →  checks out a connection from the pool
    run_query / execute_transaction  →  check out → use → return (via close)

pyodbc supports driver-level pooling via pyodbc.pooling = True (which is the
default). Combined with @st.cache_resource caching the resolved connection
string, this ensures that:
    1. Config resolution happens once per server boot (not per query)
    2. pyodbc's internal ODBC connection pool is properly reused
    3. Retry logic only fires on genuine transient failures, not pool exhaustion
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any, Dict, List, Tuple

import pyodbc
import pandas as pd
import streamlit as st

logger = logging.getLogger(__name__)

# ─── Ensure ODBC-level connection pooling is enabled ───
# This is True by default in pyodbc, but we make it explicit.
pyodbc.pooling = True


# ─────────────────────────────────────────────────────────
# Connection Pool (singleton per Streamlit server process)
# ─────────────────────────────────────────────────────────

def _resolve_database_config() -> Dict[str, Any]:
    """Resolve DB config using environment profile with secrets fallback."""
    app_env = os.getenv("COHABITANT_ENV", "development").lower()

    if "database_profiles" in st.secrets:
        profiles = st.secrets["database_profiles"]
        if app_env in profiles:
            cfg = dict(profiles[app_env])
            logger.info("Using database profile '%s' from secrets", app_env)
            return cfg

    if "database" in st.secrets:
        cfg = dict(st.secrets["database"])
        logger.info("Using default database profile from secrets")
        return cfg

    raise Exception(
        "Missing database configuration. Add [database] or [database_profiles.<env>] "
        "to .streamlit/secrets.toml"
    )


def _build_connection_string(cfg: Dict[str, Any]) -> str:
    """Build SQL Server connection string from resolved config."""
    server = cfg.get("server")
    database = cfg.get("database")
    driver = cfg.get("driver", "{ODBC Driver 17 for SQL Server}")
    trusted_connection = str(cfg.get("trusted_connection", "yes")).lower()

    if not server or not database:
        raise Exception("Database config requires 'server' and 'database'.")

    if trusted_connection == "yes":
        return (
            f"DRIVER={driver};"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes;"
        )

    username = cfg.get("username")
    password = cfg.get("password")
    if not username or not password:
        raise Exception("SQL auth requires 'username' and 'password'.")

    return (
        f"DRIVER={driver};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={username};"
        f"PWD={password};"
    )


@st.cache_resource(show_spinner=False)
def _init_connection_pool() -> str:
    """
    Resolve and cache the connection string once per server lifetime.

    By caching the resolved string (not the connection object), we avoid
    Streamlit's restriction on caching non-hashable pyodbc.Connection
    objects while still eliminating repeated secrets/config resolution.

    The actual pooling is handled by pyodbc's ODBC Driver Manager pool
    (pyodbc.pooling = True), which reuses physical TCP connections
    transparently when .close() is called.

    Returns:
        str: Fully resolved ODBC connection string
    """
    cfg = _resolve_database_config()
    conn_str = _build_connection_string(cfg)
    server = cfg.get("server")
    database = cfg.get("database")
    logger.info("🔌 Connection pool initialized for %s on %s", database, server)
    return conn_str


def get_db_connection(max_retries: int = 3, base_delay_seconds: float = 0.4):
    """
    Check out a connection from the pool with retry logic.

    Uses the cached connection string from _init_connection_pool() and
    pyodbc's ODBC-level pooling. When the caller calls conn.close(),
    the physical connection is returned to the pool — not destroyed.

    Returns:
        pyodbc.Connection: Active database connection

    Raises:
        Exception: If all retry attempts fail
    """
    conn_str = _init_connection_pool()

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            connection = pyodbc.connect(conn_str, timeout=8)
            connection.setdecoding(pyodbc.SQL_CHAR, encoding="utf-8")
            connection.setdecoding(pyodbc.SQL_WCHAR, encoding="utf-8")
            if attempt > 1:
                logger.info("✅ Connection acquired on retry attempt %s", attempt)
            return connection
        except pyodbc.Error as exc:
            last_error = exc
            logger.warning("DB connection attempt %s/%s failed: %s", attempt, max_retries, exc)
            if attempt < max_retries:
                time.sleep(base_delay_seconds * (2 ** (attempt - 1)))

    logger.error("❌ Database connection failed after retries: %s", last_error)
    raise Exception(f"Failed to connect to database after {max_retries} attempts: {last_error}")


# ─────────────────────────────────────────────────────────
# Query Execution
# ─────────────────────────────────────────────────────────

def run_query(sql: str, params: List[Any] = None) -> pd.DataFrame:
    """
    Execute a SELECT query and return results as a pandas DataFrame.

    Connection is checked out from pool, used, then returned via close().
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        columns = [desc[0] for desc in cursor.description]
        rows = [tuple(row) for row in cursor.fetchall()]
        df = pd.DataFrame(rows, columns=columns)

        clean_sql = sql.replace('\n', ' ').strip()
        logger.info("✅ Query Success (%s rows) | SQL: %s...", len(df), clean_sql[:50])
        return df

    except pyodbc.Error as e:
        logger.error("❌ Query execution failed: %s\nSQL: %s", e, sql)
        raise Exception(f"Query failed: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()  # Returns connection to ODBC pool


def execute_transaction(
    sql: str,
    params: List[Any] = None,
    return_output_params: bool = False,
) -> Tuple[int, Dict[str, Any]]:
    """
    Execute a DML statement or stored procedure with transaction management.

    Connection is checked out from pool, used within a transaction, then
    returned via close().
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        # Try to fetch a scalar return payload if one exists
        try:
            fetched = cursor.fetchval()
            return_code = int(fetched) if fetched is not None else 0
        except (pyodbc.ProgrammingError, TypeError, ValueError):
            return_code = 0

        conn.commit()
        clean_sql = sql.replace('\n', ' ').strip()
        logger.info("✅ Transaction Success! Return: %s | Executed: %s...", return_code, clean_sql[:50])

        return return_code, {}

    except pyodbc.Error as e:
        if conn:
            conn.rollback()
        logger.error("❌ Transaction failed and rolled back: %s\nSQL: %s", e, sql)
        raise Exception(f"Transaction failed: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()  # Returns connection to ODBC pool


# ─────────────────────────────────────────────────────────
# Tenant-Scoped Helpers
# ─────────────────────────────────────────────────────────

def get_tenant_property_id(tenant_id: int) -> int | None:
    """Return the active Property_ID for a tenant, or None if no active lease exists."""
    sql = """
    SELECT TOP 1 la.Property_ID
    FROM dbo.LEASE_AGREEMENT la
    WHERE la.Tenant_ID = ?
      AND la.Is_Active = 1
      AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
    ORDER BY la.End_Date DESC, la.Lease_ID DESC
    """
    df = run_query(sql, [tenant_id])
    if df.empty:
        return None
    return int(df.iloc[0]["Property_ID"])


def get_roommate_ids(tenant_id: int) -> list[int]:
    """Return all active Tenant_IDs in the same active property as the given tenant."""
    property_id = get_tenant_property_id(tenant_id)
    if property_id is None:
        return []

    sql = """
    SELECT DISTINCT la.Tenant_ID
    FROM dbo.LEASE_AGREEMENT la
    WHERE la.Property_ID = ?
      AND la.Is_Active = 1
      AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
    ORDER BY la.Tenant_ID
    """
    df = run_query(sql, [property_id])
    if df.empty:
        return []
    return [int(row["Tenant_ID"]) for _, row in df.iterrows()]


def load_roommates_details(tenant_id: int) -> pd.DataFrame:
    """Return roommate contact details for tenants sharing the same active property."""
    roommate_ids = [rid for rid in get_roommate_ids(tenant_id) if rid != tenant_id]
    if not roommate_ids:
        return pd.DataFrame(columns=["First_Name", "Last_Name", "Email", "Phone_Number"])

    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT p.First_Name, p.Last_Name, p.Email, p.Phone_Number
    FROM dbo.TENANT t
    INNER JOIN dbo.PERSON p ON p.Person_ID = t.Tenant_ID
    WHERE t.Tenant_ID IN ({placeholders}) AND t.Is_Active = 1
    ORDER BY p.First_Name, p.Last_Name
    """
    return run_query(sql, roommate_ids)


def get_active_tenants(tenant_id: int | None = None) -> pd.DataFrame:
    """Fetch active tenants, optionally scoped to the same property."""
    if tenant_id is None:
        sql = """
        SELECT t.Tenant_ID, p.First_Name + ' ' + p.Last_Name AS Full_Name, p.Email
        FROM dbo.TENANT t
        JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
        WHERE t.Is_Active = 1
        ORDER BY p.First_Name
        """
        return run_query(sql)

    roommate_ids = get_roommate_ids(tenant_id)
    if not roommate_ids:
        return pd.DataFrame(columns=["Tenant_ID", "Full_Name", "Email"])

    placeholders = ", ".join("?" for _ in roommate_ids)
    sql = f"""
    SELECT t.Tenant_ID, p.First_Name + ' ' + p.Last_Name AS Full_Name, p.Email
    FROM dbo.TENANT t
    INNER JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
    WHERE t.Tenant_ID IN ({placeholders}) AND t.Is_Active = 1
    ORDER BY p.First_Name, p.Last_Name
    """
    return run_query(sql, roommate_ids)


def get_tenant_name(tenant_id: int) -> str:
    """Fetch the full name of a specific tenant."""
    sql = """
    SELECT p.First_Name + ' ' + p.Last_Name AS Full_Name
    FROM dbo.TENANT t
    JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
    WHERE t.Tenant_ID = ?
    """
    try:
        df = run_query(sql, [tenant_id])
        return df['Full_Name'].iloc[0] if len(df) > 0 else "Unknown"
    except Exception as e:
        logger.error("Failed to fetch tenant name for ID %s: %s", tenant_id, e)
        return "Unknown"
