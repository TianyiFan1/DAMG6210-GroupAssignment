USE CoHabitant;
GO

/* =========================================================================================
   CoHabitant — Indexing Strategy
   =========================================================================================
   
   This script demonstrates a complete indexing strategy for the CoHabitant
   shared-living management database. It covers:
   
     PART 1: Discover — Missing indexes & unused indexes (DMVs)
     PART 2: Clustered Indexes — Observe existing PKs
     PART 3: Non-Clustered Indexes — Basic, Covering (INCLUDE), Composite, Filtered
     PART 4: Columnstore Index — Analytics aggregations (utility time-series)
     PART 5: Full-Text Index — Natural language search on proposals
     PART 6: Validation — Execution plans + SET STATISTICS IO
     PART 7: Maintenance — Fragmentation check, REORGANIZE, REBUILD
   
========================================================================================= */


/* =========================================================================================
   PART 1: DISCOVER — Find Missing Indexes & Unused Indexes
   
   Run these FIRST against your live database before creating any new indexes.
   SQL Server's DMVs track which queries would benefit from indexes that
   don't exist, and which existing indexes are never used.
========================================================================================= */

-- 1a. Missing Indexes — SQL Server recommends these based on query patterns
SELECT TOP 10
    ROUND(migs.avg_total_user_cost * migs.avg_user_impact
          * (migs.user_seeks + migs.user_scans), 0)       AS ImprovementScore,
    mid.statement                                          AS TableName,
    mid.equality_columns,
    mid.inequality_columns,
    mid.included_columns
FROM   sys.dm_db_missing_index_groups        mig
JOIN   sys.dm_db_missing_index_group_stats   migs
    ON mig.index_group_handle = migs.group_handle
JOIN   sys.dm_db_missing_index_details       mid
    ON mig.index_handle = mid.index_handle
WHERE  mid.database_id = DB_ID('CoHabitant')
ORDER  BY ImprovementScore DESC;
GO

-- 1b. Unused Indexes — indexes that exist but are never seeked or scanned
--     These are candidates for removal (they still cost writes on every DML)
SELECT OBJECT_NAME(i.object_id) AS TableName,
       i.name                   AS IndexName,
       i.type_desc,
       ISNULL(us.user_seeks, 0)   AS Seeks,
       ISNULL(us.user_scans, 0)   AS Scans,
       ISNULL(us.user_lookups, 0) AS Lookups,
       ISNULL(us.user_updates, 0) AS Updates   -- every INSERT/UPDATE/DELETE still costs this
FROM   sys.indexes i
LEFT   JOIN sys.dm_db_index_usage_stats us
    ON us.object_id = i.object_id
   AND us.index_id  = i.index_id
   AND us.database_id = DB_ID()
WHERE  OBJECTPROPERTY(i.object_id, 'IsUserTable') = 1
   AND i.type_desc <> 'HEAP'
   AND i.is_primary_key = 0        -- don't suggest dropping PKs
   AND i.is_unique_constraint = 0  -- don't suggest dropping unique constraints
ORDER  BY (ISNULL(us.user_seeks, 0) + ISNULL(us.user_scans, 0)) ASC,
          ISNULL(us.user_updates, 0) DESC;
GO

-- 1c. Index Usage Stats — see which indexes are actually being used
SELECT OBJECT_NAME(i.object_id) AS TableName,
       i.name                   AS IndexName,
       i.type_desc,
       us.user_seeks,
       us.user_scans,
       us.user_lookups,
       us.user_updates,
       us.last_user_seek,
       us.last_user_scan
FROM   sys.dm_db_index_usage_stats us
JOIN   sys.indexes i
    ON us.object_id = i.object_id
   AND us.index_id  = i.index_id
WHERE  us.database_id = DB_ID()
   AND OBJECTPROPERTY(i.object_id, 'IsUserTable') = 1
ORDER  BY us.user_seeks + us.user_scans DESC;
GO


/* =========================================================================================
   PART 2: CLUSTERED INDEXES — Observe Existing Primary Keys
   
   Every table with a PRIMARY KEY automatically gets a clustered index.
   The clustered index determines the physical sort order of rows on disk.
   CoHabitant has 18+ tables, each with a clustered PK.
========================================================================================= */

-- 2a. List all clustered indexes in the database
SELECT t.name       AS TableName,
       i.name       AS IndexName,
       i.type_desc,
       i.is_primary_key,
       i.is_unique
FROM   sys.indexes i
JOIN   sys.tables  t ON i.object_id = t.object_id
WHERE  i.type_desc = 'CLUSTERED'
ORDER  BY t.name;
GO

-- 2b. Demonstrate Clustered Index Seek — direct B-Tree lookup, very fast
SET STATISTICS IO ON;

-- Single-row seek on PK (Clustered Index Seek)
SELECT Expense_ID, Paid_By_Tenant_ID, Total_Amount, Date_Incurred
FROM   dbo.EXPENSE
WHERE  Expense_ID = 1;
-- Execution Plan: Clustered Index Seek
-- Expected: ~2 logical reads

-- Range scan on PK (still uses clustered index, scans contiguous leaf pages)
SELECT Tenant_ID, Current_Net_Balance, Tenant_Responsibility_Score
FROM   dbo.TENANT
WHERE  Tenant_ID BETWEEN 11 AND 16
ORDER  BY Tenant_ID;
-- Execution Plan: Clustered Index Seek (range)

SET STATISTICS IO OFF;
GO


/* =========================================================================================
   PART 3: NON-CLUSTERED INDEXES
   
   Demonstrates the progression:
     3a. Basic NC Index       — causes Key Lookup (expensive)
     3b. Covering Index       — eliminates Key Lookup via INCLUDE
     3c. Composite Index      — multi-column key for range + sort
     3d. Filtered Indexes     — WHERE Is_Active = 1 (our production indexes)
========================================================================================= */

-- ─────────────────────────────────────────────────────────
-- 3a. Basic NC Index — demonstrates Key Lookup problem
-- ─────────────────────────────────────────────────────────

CREATE NONCLUSTERED INDEX IX_Person_Email_Basic
    ON dbo.PERSON (Email);
GO

SET STATISTICS IO ON;

-- This query triggers: NC Index Seek → Key Lookup (extra I/O per row)
SELECT Person_ID, First_Name, Last_Name, Email, Phone_Number
FROM   dbo.PERSON
WHERE  Email = 'kmalone.tenant@email.com';
-- Check execution plan: "Key Lookup" operator ← expensive for large result sets

SET STATISTICS IO OFF;

-- Drop basic index before creating covering version
DROP INDEX IX_Person_Email_Basic ON dbo.PERSON;
GO


-- ─────────────────────────────────────────────────────────
-- 3b. Covering Index — eliminates Key Lookup with INCLUDE
-- ─────────────────────────────────────────────────────────

CREATE NONCLUSTERED INDEX IX_Person_Email_Cover
    ON dbo.PERSON (Email)
    INCLUDE (First_Name, Last_Name, Phone_Number);
GO

SET STATISTICS IO ON;

-- SAME query, but now all columns are in the index → no Key Lookup
SELECT Person_ID, First_Name, Last_Name, Email, Phone_Number
FROM   dbo.PERSON
WHERE  Email = 'kmalone.tenant@email.com';
-- Execution Plan: Index Seek only (no Key Lookup!) ← much cheaper

SET STATISTICS IO OFF;

DROP INDEX IX_Person_Email_Cover ON dbo.PERSON;
GO


-- ─────────────────────────────────────────────────────────
-- 3c. Composite Index — multi-column key for range + sort
-- ─────────────────────────────────────────────────────────

-- Find utility readings for a specific property sorted by date
CREATE NONCLUSTERED INDEX IX_UtilityReading_Property_Date
    ON dbo.UTILITY_READING (Property_ID, Reading_Date DESC)
    INCLUDE (Utility_Type_ID, Meter_Value, Provider_Name);
GO

SET STATISTICS IO ON;

SELECT Reading_Date, Utility_Type_ID, Provider_Name, Meter_Value
FROM   dbo.UTILITY_READING
WHERE  Property_ID = 1
ORDER  BY Reading_Date DESC;
-- Plan: Index Seek on (Property_ID=1), rows already sorted by Reading_Date DESC ✓

SET STATISTICS IO OFF;

DROP INDEX IX_UtilityReading_Property_Date ON dbo.UTILITY_READING;
GO


-- ─────────────────────────────────────────────────────────
-- 3d. Filtered Indexes — Production indexes for CoHabitant
--     WHERE Is_Active = 1 excludes soft-deleted rows
-- ─────────────────────────────────────────────────────────

-- These are the actual production indexes used by the Streamlit app and SPs.
-- Filtered predicates keep index sizes small and ensure seeks only touch live data.

-- Index 1: Financial Dashboard — expense lookups by date and payer
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Expense_Date_Tenant' AND object_id = OBJECT_ID('dbo.EXPENSE'))
    DROP INDEX idx_Expense_Date_Tenant ON dbo.EXPENSE;
GO
CREATE NONCLUSTERED INDEX idx_Expense_Date_Tenant
ON dbo.EXPENSE (Date_Incurred DESC, Paid_By_Tenant_ID)
INCLUDE (Total_Amount, Split_Policy)
WHERE Is_Active = 1;
GO

-- Index 2: Roommate Debt — expense share lookups for settle-up calculations
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_ExpenseShare_OwedBy' AND object_id = OBJECT_ID('dbo.EXPENSE_SHARE'))
    DROP INDEX idx_ExpenseShare_OwedBy ON dbo.EXPENSE_SHARE;
GO
CREATE NONCLUSTERED INDEX idx_ExpenseShare_OwedBy
ON dbo.EXPENSE_SHARE (Owed_By_Tenant_ID, Status)
INCLUDE (Expense_ID, Owed_Amount)
WHERE Is_Active = 1;
GO

-- Index 3: Chore Assignment — pending chore lookups per tenant
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Chore_AssignedTenant' AND object_id = OBJECT_ID('dbo.CHORE_ASSIGNMENT'))
    DROP INDEX idx_Chore_AssignedTenant ON dbo.CHORE_ASSIGNMENT;
GO
CREATE NONCLUSTERED INDEX idx_Chore_AssignedTenant
ON dbo.CHORE_ASSIGNMENT (Assigned_Tenant_ID, Status)
INCLUDE (Chore_ID, Due_Date)
WHERE Is_Active = 1;
GO

-- Index 4: Active Lease Lookup — property scoping for roommate isolation
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Lease_Tenant_Active' AND object_id = OBJECT_ID('dbo.LEASE_AGREEMENT'))
    DROP INDEX idx_Lease_Tenant_Active ON dbo.LEASE_AGREEMENT;
GO
CREATE NONCLUSTERED INDEX idx_Lease_Tenant_Active
ON dbo.LEASE_AGREEMENT (Tenant_ID, Start_Date, End_Date)
INCLUDE (Property_ID)
WHERE Is_Active = 1;
GO

-- Index 5: Payment Settlement — settle-up CTE queries for pairwise balances
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Payment_Payer_Type' AND object_id = OBJECT_ID('dbo.PAYMENT'))
    DROP INDEX idx_Payment_Payer_Type ON dbo.PAYMENT;
GO
CREATE NONCLUSTERED INDEX idx_Payment_Payer_Type
ON dbo.PAYMENT (Payer_Tenant_ID, Payment_Type)
INCLUDE (Payee_Tenant_ID, Amount)
WHERE Is_Active = 1;
GO

-- Validate: confirm all 5 filtered indexes are in place
SELECT i.name, i.type_desc, i.has_filter, i.filter_definition,
       OBJECT_NAME(i.object_id) AS TableName
FROM   sys.indexes i
WHERE  i.has_filter = 1
   AND OBJECTPROPERTY(i.object_id, 'IsUserTable') = 1
ORDER  BY OBJECT_NAME(i.object_id), i.name;
GO


/* =========================================================================================
   PART 4: COLUMNSTORE INDEX — Analytics Aggregations
   
   The UTILITY_READING table powers the Analytics dashboard (utility trends,
   month-over-month comparisons, category breakdowns). These are classic
   OLAP-style GROUP BY queries that benefit from Columnstore batch-mode
   processing and columnar compression.
   
   We use a Non-Clustered Columnstore Index (NCCI) so the underlying
   rowstore remains intact for OLTP inserts from the Landlord Portal.
========================================================================================= */

SET STATISTICS IO ON;
SET STATISTICS TIME ON;

-- BEFORE Columnstore: row-by-row scan with row-mode aggregation
SELECT   p.Property_ID,
         ut.Type_Name           AS Utility_Category,
         YEAR(ur.Reading_Date)  AS Reading_Year,
         MONTH(ur.Reading_Date) AS Reading_Month,
         COUNT(*)               AS Reading_Count,
         SUM(ur.Meter_Value)    AS Total_Cost,
         AVG(ur.Meter_Value)    AS Avg_Cost
FROM     dbo.UTILITY_READING ur
JOIN     dbo.UTILITY_TYPE ut ON ur.Utility_Type_ID = ut.Utility_Type_ID
JOIN     dbo.PROPERTY p      ON ur.Property_ID = p.Property_ID
WHERE    ur.Is_Active = 1
GROUP BY p.Property_ID, ut.Type_Name,
         YEAR(ur.Reading_Date), MONTH(ur.Reading_Date)
ORDER BY p.Property_ID, Reading_Year, Reading_Month;
-- Record: logical reads, CPU time

SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO

-- Create Non-Clustered Columnstore Index
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'NCCI_UtilityReading_Analytics' AND object_id = OBJECT_ID('dbo.UTILITY_READING'))
    DROP INDEX NCCI_UtilityReading_Analytics ON dbo.UTILITY_READING;
GO

CREATE NONCLUSTERED COLUMNSTORE INDEX NCCI_UtilityReading_Analytics
    ON dbo.UTILITY_READING (Property_ID, Utility_Type_ID, Meter_Value, Reading_Date);
GO

SET STATISTICS IO ON;
SET STATISTICS TIME ON;

-- AFTER Columnstore: re-run the SAME query
-- Compare: logical reads ↓, Batch Mode appears in execution plan ✓
SELECT   p.Property_ID,
         ut.Type_Name           AS Utility_Category,
         YEAR(ur.Reading_Date)  AS Reading_Year,
         MONTH(ur.Reading_Date) AS Reading_Month,
         COUNT(*)               AS Reading_Count,
         SUM(ur.Meter_Value)    AS Total_Cost,
         AVG(ur.Meter_Value)    AS Avg_Cost
FROM     dbo.UTILITY_READING ur
JOIN     dbo.UTILITY_TYPE ut ON ur.Utility_Type_ID = ut.Utility_Type_ID
JOIN     dbo.PROPERTY p      ON ur.Property_ID = p.Property_ID
WHERE    ur.Is_Active = 1
GROUP BY p.Property_ID, ut.Type_Name,
         YEAR(ur.Reading_Date), MONTH(ur.Reading_Date)
ORDER BY p.Property_ID, Reading_Year, Reading_Month;

SET STATISTICS IO OFF;
SET STATISTICS TIME OFF;
GO

-- Inspect columnstore segment metadata
SELECT   col.name            AS ColumnName,
         seg.row_count,
         seg.on_disk_size    AS DiskBytes,
         seg.min_data_id,
         seg.max_data_id
FROM     sys.column_store_segments  seg
JOIN     sys.partitions             p
    ON   seg.partition_id = p.partition_id
JOIN     sys.columns                col
    ON   col.object_id = p.object_id
    AND  col.column_id = seg.column_id
WHERE    p.object_id = OBJECT_ID('dbo.UTILITY_READING')
ORDER BY col.name;
GO


/* =========================================================================================
   PART 5: FULL-TEXT INDEX — Natural Language Search on Proposals
   
   The PROPOSAL table has a Description column (VARCHAR 255) that tenants
   use to describe house rules. Full-Text Search enables CONTAINS (exact),
   FREETEXT (relaxed), and ranked FREETEXTTABLE queries.
========================================================================================= */

-- Check if Full-Text Search is installed
SELECT SERVERPROPERTY('IsFullTextInstalled') AS FullTextInstalled;
-- If this returns 0, Full-Text is not available on this instance.
-- The script below handles both cases gracefully.
GO

-- Conditionally create Full-Text Catalog + Index + demo queries
-- Only executes if Full-Text Search is installed (returns 1)
IF CAST(SERVERPROPERTY('IsFullTextInstalled') AS INT) = 1
BEGIN
    -- Create Full-Text Catalog (container for FT indexes)
    IF NOT EXISTS (SELECT * FROM sys.fulltext_catalogs WHERE name = 'FTC_CoHabitant')
        CREATE FULLTEXT CATALOG FTC_CoHabitant AS DEFAULT;

    PRINT '✅ Full-Text Catalog FTC_CoHabitant created (or already exists).';
END
ELSE
BEGIN
    PRINT '⚠️  Full-Text Search is NOT installed on this SQL Server instance.';
    PRINT '    Skipping Full-Text Catalog and Index creation.';
    PRINT '    To install: run SQL Server Setup → Add Features → Full-Text Search.';
    PRINT '    Azure SQL Database supports Full-Text Search on all tiers.';
END
GO

-- Create Full-Text Index on PROPOSAL.Description
-- KEY INDEX must reference the PK of the table
-- Using dynamic SQL because KEY INDEX requires a literal index name
IF CAST(SERVERPROPERTY('IsFullTextInstalled') AS INT) = 1
BEGIN
    DECLARE @PKIndexName NVARCHAR(128);
    SELECT @PKIndexName = i.name
    FROM   sys.indexes i
    WHERE  i.object_id = OBJECT_ID('dbo.PROPOSAL')
       AND i.is_primary_key = 1;

    DECLARE @FTSql NVARCHAR(MAX);

    IF NOT EXISTS (SELECT * FROM sys.fulltext_indexes WHERE object_id = OBJECT_ID('dbo.PROPOSAL'))
    BEGIN
        SET @FTSql = N'CREATE FULLTEXT INDEX ON dbo.PROPOSAL (Description LANGUAGE 1033)
            KEY INDEX ' + QUOTENAME(@PKIndexName) + N'
            ON FTC_CoHabitant
            WITH CHANGE_TRACKING AUTO;';
        EXEC sp_executesql @FTSql;
        PRINT '✅ Full-Text Index created on PROPOSAL.Description.';
    END
    ELSE
        PRINT '✅ Full-Text Index already exists on PROPOSAL.Description.';
END
GO

-- Wait for population (small table — should be instant)
IF CAST(SERVERPROPERTY('IsFullTextInstalled') AS INT) = 1
    SELECT FULLTEXTCATALOGPROPERTY('FTC_CoHabitant', 'PopulateStatus') AS PopulateStatus;
    -- 0 = idle (done), 1 = in progress
GO

-- CONTAINS: exact word match
IF CAST(SERVERPROPERTY('IsFullTextInstalled') AS INT) = 1
    EXEC sp_executesql N'SELECT Proposal_ID, Description, Status
    FROM dbo.PROPOSAL WHERE CONTAINS(Description, ''cleaning'')';
GO

-- CONTAINS: prefix match (matches: internet, interior, ...)
IF CAST(SERVERPROPERTY('IsFullTextInstalled') AS INT) = 1
    EXEC sp_executesql N'SELECT Proposal_ID, Description, Status
    FROM dbo.PROPOSAL WHERE CONTAINS(Description, ''"internet*"'')';
GO

-- FREETEXT: relaxed/semantic match (finds related terms)
IF CAST(SERVERPROPERTY('IsFullTextInstalled') AS INT) = 1
    EXEC sp_executesql N'SELECT Proposal_ID, Description, Status
    FROM dbo.PROPOSAL WHERE FREETEXT(Description, ''shared household expenses cost'')';
GO

-- FREETEXTTABLE: ranked results with relevance scores
IF CAST(SERVERPROPERTY('IsFullTextInstalled') AS INT) = 1
    EXEC sp_executesql N'SELECT p.Proposal_ID, p.Description, p.Status, ft.[RANK]
    FROM FREETEXTTABLE(dbo.PROPOSAL, Description, ''quiet hours night rules'') ft
    JOIN dbo.PROPOSAL p ON ft.[KEY] = p.Proposal_ID
    ORDER BY ft.[RANK] DESC';
GO


/* =========================================================================================
   PART 6: VALIDATION — Index Usage Stats After Queries
   
   After running the application or the queries above, these DMVs show
   which indexes are actually being used and how effective they are.
========================================================================================= */

-- 6a. Usage stats for all CoHabitant user indexes
SELECT OBJECT_NAME(i.object_id) AS TableName,
       i.name                   AS IndexName,
       i.type_desc,
       ISNULL(us.user_seeks, 0)   AS Seeks,
       ISNULL(us.user_scans, 0)   AS Scans,
       ISNULL(us.user_lookups, 0) AS Lookups,
       ISNULL(us.user_updates, 0) AS Updates
FROM   sys.indexes i
LEFT   JOIN sys.dm_db_index_usage_stats us
    ON us.object_id = i.object_id
   AND us.index_id  = i.index_id
   AND us.database_id = DB_ID()
WHERE  OBJECTPROPERTY(i.object_id, 'IsUserTable') = 1
   AND i.type > 0  -- exclude heaps
ORDER  BY OBJECT_NAME(i.object_id), i.name;
GO

-- 6b. Validate filtered indexes are being used by the Streamlit app queries
-- Run a sample query and check that our filtered index is seeked
SET STATISTICS IO ON;

-- This should use idx_Lease_Tenant_Active (filtered, covering)
SELECT la.Property_ID
FROM   dbo.LEASE_AGREEMENT la
WHERE  la.Tenant_ID = 11
  AND  la.Is_Active = 1
  AND  CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date;

-- This should use idx_ExpenseShare_OwedBy (filtered, covering)
SELECT es.Expense_ID, es.Owed_Amount, es.Status
FROM   dbo.EXPENSE_SHARE es
WHERE  es.Owed_By_Tenant_ID = 12
  AND  es.Status = 'Pending'
  AND  es.Is_Active = 1;

SET STATISTICS IO OFF;
GO


/* =========================================================================================
   PART 7: MAINTENANCE — Fragmentation Check + REORGANIZE / REBUILD
   
   Over time, DML operations (INSERT, UPDATE, DELETE) cause index
   fragmentation — logical ordering of pages diverges from physical order.
   
   Decision matrix:
     < 10% fragmentation  → Do nothing
     10–30% fragmentation → ALTER INDEX ... REORGANIZE (online, low lock)
     > 30% fragmentation  → ALTER INDEX ... REBUILD (offline, faster)
========================================================================================= */

-- 7a. Check fragmentation across all indexes in the database
SELECT OBJECT_NAME(ips.object_id) AS TableName,
       i.name                     AS IndexName,
       i.type_desc,
       ips.avg_fragmentation_in_percent,
       ips.page_count,
       ips.fragment_count
FROM   sys.dm_db_index_physical_stats(
           DB_ID(), NULL, NULL, NULL, 'LIMITED') ips
JOIN   sys.indexes i
    ON ips.object_id = i.object_id
   AND ips.index_id  = i.index_id
WHERE  OBJECTPROPERTY(ips.object_id, 'IsUserTable') = 1
   AND ips.page_count > 0          -- skip empty indexes
   AND i.type > 0                  -- skip heaps
ORDER  BY ips.avg_fragmentation_in_percent DESC;
GO

-- 7b. REORGANIZE example — online, minimal locking (for 10-30% fragmentation)
-- Reorganizes leaf pages of the specified index
ALTER INDEX idx_Expense_Date_Tenant ON dbo.EXPENSE REORGANIZE;
GO

-- 7c. REBUILD example — rebuilds entire index structure (for >30% fragmentation)
-- FILLFACTOR = 80 leaves 20% free space on each page to reduce future splits
ALTER INDEX ALL ON dbo.LEASE_AGREEMENT REBUILD WITH (FILLFACTOR = 80);
GO

-- 7d. Verify fragmentation after maintenance
SELECT OBJECT_NAME(ips.object_id) AS TableName,
       i.name                     AS IndexName,
       ips.avg_fragmentation_in_percent,
       ips.page_count
FROM   sys.dm_db_index_physical_stats(
           DB_ID(), OBJECT_ID('dbo.EXPENSE'), NULL, NULL, 'LIMITED') ips
JOIN   sys.indexes i
    ON ips.object_id = i.object_id
   AND ips.index_id  = i.index_id
WHERE  ips.page_count > 0;
GO


/* =========================================================================================
   SUMMARY — Index Inventory for CoHabitant
   =========================================================================================
   
   Type                  | Count | Tables
   ─────────────────────────────────────────────────────────
   Clustered (PK)        |  18+  | All tables (auto-created by PRIMARY KEY)
   Non-Clustered Basic   |   -   | Demonstrated on PERSON.Email (created and dropped)
   Non-Clustered Covering|   -   | Demonstrated on PERSON.Email + INCLUDE (created and dropped)
   Non-Clustered Composi.|   -   | Demonstrated on UTILITY_READING (created and dropped)
   Filtered NC (prod)    |   5   | EXPENSE, EXPENSE_SHARE, CHORE_ASSIGNMENT, LEASE_AGREEMENT, PAYMENT
   Columnstore (NCCI)    |   1   | UTILITY_READING (analytics dashboard)
   Full-Text             |   1   | PROPOSAL (natural language search on descriptions)
   ─────────────────────────────────────────────────────────
   
   DMV Queries Included:
     - sys.dm_db_missing_index_*     → Find indexes SQL Server recommends
     - sys.dm_db_index_usage_stats   → Validate which indexes are actually used
     - sys.dm_db_index_physical_stats→ Check fragmentation levels
     - sys.column_store_segments     → Columnstore segment metadata
   
   Maintenance Strategy:
     - < 10% fragmentation  → No action
     - 10-30% fragmentation → REORGANIZE (online)
     - > 30% fragmentation  → REBUILD WITH (FILLFACTOR = 80)
   
========================================================================================= */