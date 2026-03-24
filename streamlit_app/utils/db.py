"""
Database layer for CoHabitant application.
Provides connection pooling, query execution, and transaction management.
"""

import logging
import pyodbc
import pandas as pd
import streamlit as st
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)


@st.cache_resource
def get_db_connection():
    """
    Returns a cached database connection singleton.
    Uses st.secrets to load connection string from .streamlit/secrets.toml.
    
    Returns:
        pyodbc.Connection: Active database connection to CoHabitant DB
        
    Raises:
        Exception: If connection fails or secrets are missing
    """
    try:
        server = st.secrets["database"]["server"]
        database = st.secrets["database"]["database"]
        driver = st.secrets["database"]["driver"]
        trusted_connection = st.secrets["database"].get("trusted_connection", "yes")
        
        # Build connection string based on authentication method
        if trusted_connection.lower() == "yes":
            # Windows Authentication
            conn_str = (
                f"DRIVER={driver};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"Trusted_Connection=yes;"
            )
        else:
            # SQL Server Authentication
            username = st.secrets["database"]["username"]
            password = st.secrets["database"]["password"]
            conn_str = (
                f"DRIVER={driver};"
                f"SERVER={server};"
                f"DATABASE={database};"
                f"UID={username};"
                f"PWD={password};"
            )
        
        connection = pyodbc.connect(conn_str)
        connection.setdecoding(pyodbc.SQL_CHAR, encoding='utf-8')
        connection.setdecoding(pyodbc.SQL_WCHAR, encoding='utf-8')
        logger.info(f"✅ Connected to {database} on {server}")
        return connection
        
    except KeyError as e:
        logger.error(f"❌ Missing database secret: {e}")
        raise Exception(
            f"Missing secret configuration. Please ensure .streamlit/secrets.toml has all required keys: {e}"
        )
    except pyodbc.Error as e:
        logger.error(f"❌ Database connection failed: {e}")
        raise Exception(f"Failed to connect to database: {e}")


def run_query(sql: str, params: List[Any] = None) -> pd.DataFrame:
    """
    Execute a SELECT query and return results as a pandas DataFrame.
    Used for reading from views and running reports.
    
    Args:
        sql: SQL SELECT query (can include parameterized placeholders ?)
        params: List of parameter values to safely inject into query
        
    Returns:
        pd.DataFrame: Query results
        
    Raises:
        Exception: If query execution fails
    """
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        # Fetch column names
        columns = [desc[0] for desc in cursor.description]
        
        # Fetch all rows and convert them to standard tuples
        rows = [tuple(row) for row in cursor.fetchall()]
        df = pd.DataFrame(rows, columns=columns)
        
        clean_sql = sql.replace('\n', ' ').strip()
        logger.info(f"✅ Query Success ({len(df)} rows) | SQL: {clean_sql[:50]}...")
        return df
        
    except pyodbc.Error as e:
        logger.error(f"❌ Query execution failed: {e}\nSQL: {sql}")
        raise Exception(f"Query failed: {e}")
    finally:
        if cursor:
            cursor.close()


def execute_transaction(
    sql: str,
    params: List[Any] = None,
    return_output_params: bool = False
) -> Tuple[int, Dict[str, Any]]:
    """
    Execute a stored procedure or DML statement with transaction management.
    Used for INSERT, UPDATE, DELETE operations and stored procedures.
    
    Args:
        sql: SQL statement or stored procedure call
             For stored procs with output params, use:
             "EXEC usp_Name ?, ?, ? OUTPUT, ?"
        params: List of parameter values (both INPUT and OUTPUT placeholders)
        return_output_params: If True, attempts to capture OUTPUT parameter values
        
    Returns:
        Tuple of (return_code, output_params_dict)
        - return_code: Integer return value from stored procedure (0=success, -1=failure)
        - output_params_dict: Dictionary of OUTPUT parameter values (if applicable)
        
    Raises:
        Exception: If transaction fails (automatically rolls back)
    """
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Execute the statement/procedure with parameters
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        
        # Try to fetch return code, but skip safely if it's a basic INSERT/UPDATE/DELETE
        try:
            return_code = cursor.fetchval()
        except pyodbc.ProgrammingError:
            return_code = 0
        
        # Commit transaction
        conn.commit()
        clean_sql = sql.replace('\n', ' ').strip()
        logger.info(f"✅ Transaction Success! Return: {return_code} | Executed: {clean_sql[:50]}...")
        
        return return_code, {}
        
    except pyodbc.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"❌ Transaction failed and rolled back: {e}\nSQL: {sql}")
        raise Exception(f"Transaction failed: {e}")
    finally:
        if cursor:
            cursor.close()


def get_active_tenants() -> pd.DataFrame:
    """
    Fetch list of all active tenants for dropdown selection.
    
    Returns:
        pd.DataFrame: Tenant listing with Tenant_ID, Full_Name, Email
    """
    sql = """
    SELECT 
        t.Tenant_ID,
        p.First_Name + ' ' + p.Last_Name AS Full_Name,
        p.Email
    FROM dbo.TENANT t
    JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
    ORDER BY p.First_Name
    """
    return run_query(sql)


def get_tenant_name(tenant_id: int) -> str:
    """
    Fetch the full name of a specific tenant.
    
    Args:
        tenant_id: Tenant_ID to look up
        
    Returns:
        str: Full name of tenant, or "Unknown" if not found
    """
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
        logger.error(f"Failed to fetch tenant name for ID {tenant_id}: {e}")
        return "Unknown"
