USE CoHabitant;
GO

/* =========================================================================================
   Phase 2 Update: All indexes now use filtered predicates (WHERE Is_Active = 1)
   to exclude soft-deleted rows from index scans. This keeps index sizes small
   and ensures covering-index seeks only touch live data.
========================================================================================= */

-- 1. Financial Dashboard Index (filtered to active expenses only)
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Expense_Date_Tenant' AND object_id = OBJECT_ID('dbo.EXPENSE'))
    DROP INDEX idx_Expense_Date_Tenant ON dbo.EXPENSE;
GO
CREATE NONCLUSTERED INDEX idx_Expense_Date_Tenant
ON dbo.EXPENSE (Date_Incurred DESC, Paid_By_Tenant_ID)
INCLUDE (Total_Amount, Split_Policy)
WHERE Is_Active = 1;
GO

-- 2. Roommate Debt Index (filtered to active shares only)
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_ExpenseShare_OwedBy' AND object_id = OBJECT_ID('dbo.EXPENSE_SHARE'))
    DROP INDEX idx_ExpenseShare_OwedBy ON dbo.EXPENSE_SHARE;
GO
CREATE NONCLUSTERED INDEX idx_ExpenseShare_OwedBy
ON dbo.EXPENSE_SHARE (Owed_By_Tenant_ID, Status)
INCLUDE (Expense_ID, Owed_Amount)
WHERE Is_Active = 1;
GO

-- 3. Chore Assignment Index (filtered to active assignments only)
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Chore_AssignedTenant' AND object_id = OBJECT_ID('dbo.CHORE_ASSIGNMENT'))
    DROP INDEX idx_Chore_AssignedTenant ON dbo.CHORE_ASSIGNMENT;
GO
CREATE NONCLUSTERED INDEX idx_Chore_AssignedTenant
ON dbo.CHORE_ASSIGNMENT (Assigned_Tenant_ID, Status)
INCLUDE (Chore_ID, Due_Date)
WHERE Is_Active = 1;
GO

-- 4. Active Lease Lookup Index (filtered to active leases only)
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Lease_Tenant_Active' AND object_id = OBJECT_ID('dbo.LEASE_AGREEMENT'))
    DROP INDEX idx_Lease_Tenant_Active ON dbo.LEASE_AGREEMENT;
GO
CREATE NONCLUSTERED INDEX idx_Lease_Tenant_Active
ON dbo.LEASE_AGREEMENT (Tenant_ID, Start_Date, End_Date)
INCLUDE (Property_ID)
WHERE Is_Active = 1;
GO

-- 5. Payment Settlement Index (new: supports settle-up CTE queries)
IF EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Payment_Payer_Type' AND object_id = OBJECT_ID('dbo.PAYMENT'))
    DROP INDEX idx_Payment_Payer_Type ON dbo.PAYMENT;
GO
CREATE NONCLUSTERED INDEX idx_Payment_Payer_Type
ON dbo.PAYMENT (Payer_Tenant_ID, Payment_Type)
INCLUDE (Payee_Tenant_ID, Amount)
WHERE Is_Active = 1;
GO
