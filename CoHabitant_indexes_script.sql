USE CoHabitant;
GO

-- 1. Financial Dashboard Index 
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Expense_Date_Tenant' AND object_id = OBJECT_ID('dbo.EXPENSE'))
BEGIN
    CREATE NONCLUSTERED INDEX idx_Expense_Date_Tenant
    ON dbo.EXPENSE (Date_Incurred DESC, Paid_By_Tenant_ID)
    INCLUDE (Total_Amount, Split_Policy); 
END
GO

-- 2. Roommate Debt Index
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_ExpenseShare_OwedBy' AND object_id = OBJECT_ID('dbo.EXPENSE_SHARE'))
BEGIN
    CREATE NONCLUSTERED INDEX idx_ExpenseShare_OwedBy
    ON dbo.EXPENSE_SHARE (Owed_By_Tenant_ID, Status)
    INCLUDE (Expense_ID, Owed_Amount);
END
GO

-- 3. Chore Assignment Index
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Chore_AssignedTenant' AND object_id = OBJECT_ID('dbo.CHORE_ASSIGNMENT'))
BEGIN
    CREATE NONCLUSTERED INDEX idx_Chore_AssignedTenant
    ON dbo.CHORE_ASSIGNMENT (Assigned_Tenant_ID, Status)
    INCLUDE (Chore_ID, Due_Date);
END
GO

-- 4. Active Lease Lookup Index
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_Lease_Tenant_Active' AND object_id = OBJECT_ID('dbo.LEASE_AGREEMENT'))
BEGIN
    CREATE NONCLUSTERED INDEX idx_Lease_Tenant_Active
    ON dbo.LEASE_AGREEMENT (Tenant_ID, Start_Date, End_Date)
    INCLUDE (Property_ID);
END
GO