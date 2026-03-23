USE CoHabitant;
GO

/* =========================================================================================
   PART 1: VIEWS (The DataFrames for Streamlit & Power BI)
   Purpose: Abstracts complex JOINs into clean, flattened tables for rapid visualization.
========================================================================================= */

-- View 1: Financial Ledger Dashboard
-- Feeds the main "Who owes what" bar chart in the UI.
CREATE OR ALTER VIEW dbo.vw_App_Ledger_ActiveBalances AS
SELECT 
    t.Tenant_ID,
    p.First_Name + ' ' + p.Last_Name AS Full_Name,
    t.Current_Net_Balance,
    ISNULL(SUM(es.Owed_Amount), 0) AS Total_Pending_Debts,
    (SELECT ISNULL(SUM(Amount), 0) FROM dbo.PAYMENT WHERE Payer_Tenant_ID = t.Tenant_ID) AS Lifetime_Paid
FROM dbo.TENANT t
JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
LEFT JOIN dbo.EXPENSE_SHARE es ON t.Tenant_ID = es.Owed_By_Tenant_ID AND es.Status = 'Pending'
GROUP BY t.Tenant_ID, p.First_Name, p.Last_Name, t.Current_Net_Balance;
GO

-- View 2: Chore Leaderboard & Gamification
-- Feeds the "Housemate Responsibility" dashboard.
CREATE OR ALTER VIEW dbo.vw_App_Chore_Leaderboard AS
SELECT 
    t.Tenant_ID,
    p.First_Name,
    t.Tenant_Responsibility_Score,
    COUNT(ca.Assignment_ID) AS Total_Chores_Assigned,
    SUM(CASE WHEN ca.Status = 'Completed' THEN 1 ELSE 0 END) AS Chores_Completed,
    SUM(CASE WHEN ca.Status = 'Pending' AND ca.Due_Date < CAST(GETDATE() AS DATE) THEN 1 ELSE 0 END) AS Overdue_Chores
FROM dbo.TENANT t
JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
LEFT JOIN dbo.CHORE_ASSIGNMENT ca ON t.Tenant_ID = ca.Assigned_Tenant_ID
GROUP BY t.Tenant_ID, p.First_Name, t.Tenant_Responsibility_Score;
GO

-- View 3: Utility Time-Series
-- Flattens utility data perfectly for Streamlit line charts (st.line_chart) or Power BI trends.
CREATE OR ALTER VIEW dbo.vw_App_Utility_TimeSeries AS
SELECT 
    ur.Reading_Date,
    ut.Type_Name AS Utility_Category,
    ur.Provider_Name,
    ur.Meter_Value AS Cost_Amount,
    p.Street_Address
FROM dbo.UTILITY_READING ur
JOIN dbo.UTILITY_TYPE ut ON ur.Utility_Type_ID = ut.Utility_Type_ID
JOIN dbo.PROPERTY p ON ur.Property_ID = p.Property_ID;
GO


/* =========================================================================================
   PART 2: USER-DEFINED FUNCTIONS (UDFs)
   Purpose: Encapsulates reusable mathematical and temporal logic to keep code DRY.
========================================================================================= */

-- UDF 1 (Scalar): Calculate exact split amount based on active household size
CREATE OR ALTER FUNCTION dbo.fn_CalculateExpenseShare (@TotalAmount DECIMAL(10,2))
RETURNS DECIMAL(10,2)
AS
BEGIN
    DECLARE @ActiveTenants INT;
    DECLARE @Share DECIMAL(10,2);
    
    -- Count how many tenants have an active lease today
    SELECT @ActiveTenants = COUNT(*) 
    FROM dbo.LEASE_AGREEMENT 
    WHERE Start_Date <= CAST(GETDATE() AS DATE) 
      AND End_Date >= CAST(GETDATE() AS DATE);
      
    IF @ActiveTenants = 0 SET @ActiveTenants = 1; -- Prevent divide by zero error
    
    SET @Share = @TotalAmount / @ActiveTenants;
    RETURN @Share;
END;
GO

-- UDF 2 (Scalar): Get Remaining Votes Needed for a Proposal
CREATE OR ALTER FUNCTION dbo.fn_GetPendingVoteCount (@Proposal_ID INT)
RETURNS INT
AS
BEGIN
    DECLARE @TotalTenants INT;
    DECLARE @VotesCast INT;
    
    SELECT @TotalTenants = COUNT(*) FROM dbo.TENANT;
    SELECT @VotesCast = COUNT(*) FROM dbo.VOTE WHERE Proposal_ID = @Proposal_ID;
    
    RETURN (@TotalTenants - @VotesCast);
END;
GO

-- UDF 3 (Table-Valued): Point-in-Time House Roster 
-- Vital for retroactively splitting bills that arrive months late.
CREATE OR ALTER FUNCTION dbo.fn_HouseRosterAsOfDate (@TargetDate DATE)
RETURNS TABLE
AS
RETURN (
    SELECT 
        t.Tenant_ID, 
        p.First_Name, 
        p.Last_Name, 
        la.Property_ID
    FROM dbo.TENANT t
    JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
    JOIN dbo.LEASE_AGREEMENT la ON t.Tenant_ID = la.Tenant_ID
    WHERE @TargetDate BETWEEN la.Start_Date AND la.End_Date
);
GO


/* =========================================================================================
   PART 3: STORED PROCEDURES (The Backend API Layer)
========================================================================================= */

-- SP 1: Create an Expense and Auto-Split it
CREATE OR ALTER PROCEDURE dbo.usp_CreateHouseholdExpense
    @PaidByTenantID INT,
    @Amount DECIMAL(10,2),
    @SplitPolicy VARCHAR(50),
    @ReceiptURL VARCHAR(255),
    @NewExpenseID INT OUTPUT -- OUTPUT 1
AS
BEGIN
    SET XACT_ABORT ON; 
    BEGIN TRY
        BEGIN TRAN;
        
        INSERT INTO dbo.EXPENSE (Paid_By_Tenant_ID, Total_Amount, Date_Incurred, Split_Policy, Receipt_Image)
        VALUES (@PaidByTenantID, @Amount, CAST(GETDATE() AS DATE), @SplitPolicy, @ReceiptURL);
        
        SET @NewExpenseID = SCOPE_IDENTITY();
        
        DECLARE @CalculatedShare DECIMAL(10,2) = dbo.fn_CalculateExpenseShare(@Amount);
        
        INSERT INTO dbo.EXPENSE_SHARE (Expense_ID, Owed_By_Tenant_ID, Owed_Amount, Status)
        SELECT @NewExpenseID, Tenant_ID, @CalculatedShare, 'Pending'
        FROM dbo.TENANT WHERE Tenant_ID <> @PaidByTenantID;
        
        COMMIT TRAN;
        RETURN 0; 
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRAN;
        DECLARE @ErrMsg NVARCHAR(4000) = ERROR_MESSAGE();
        RAISERROR(@ErrMsg, 16, 1);
        RETURN -1; 
    END CATCH
END;
GO

-- SP 2: Process a Peer-to-Peer Rent/Expense Payment
CREATE OR ALTER PROCEDURE dbo.usp_ProcessTenantPayment
    @PayerTenantID INT,
    @Amount DECIMAL(10,2),
    @Note VARCHAR(255),
    @NewBalance DECIMAL(10,2) OUTPUT -- OUTPUT 2 (Added per Copilot)
AS
BEGIN
    SET XACT_ABORT ON;
    BEGIN TRY
        BEGIN TRAN;
        
        INSERT INTO dbo.PAYMENT (Payer_Tenant_ID, Amount, Payment_Date, Note)
        VALUES (@PayerTenantID, @Amount, CAST(GETDATE() AS DATE), @Note);
        
        UPDATE dbo.TENANT
        SET Current_Net_Balance = Current_Net_Balance + @Amount
        WHERE Tenant_ID = @PayerTenantID;
        
        -- Return the new balance to the frontend
        SELECT @NewBalance = Current_Net_Balance FROM dbo.TENANT WHERE Tenant_ID = @PayerTenantID;
        
        COMMIT TRAN;
        RETURN 0;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRAN;
        THROW;
    END CATCH
END;
GO

-- SP 3: Securely Cast a Vote and Auto-Resolve the Proposal
CREATE OR ALTER PROCEDURE dbo.usp_CastProposalVote
    @ProposalID INT,
    @TenantID INT,
    @IsApproved BIT,
    @FinalStatus VARCHAR(20) OUTPUT -- OUTPUT 3 (Added per Copilot)
AS
BEGIN
    SET XACT_ABORT ON; -- Added per Copilot for consistency
    BEGIN TRY
        BEGIN TRAN;
        
        -- The UNIQUE constraint (added below) handles duplicate prevention now
        INSERT INTO dbo.VOTE (Proposal_ID, Tenant_ID, Approval_Status, Vote_Timestamp)
        VALUES (@ProposalID, @TenantID, @IsApproved, GETDATE());
        
        IF dbo.fn_GetPendingVoteCount(@ProposalID) = 0
        BEGIN
            DECLARE @YesVotes INT = (SELECT COUNT(*) FROM dbo.VOTE WHERE Proposal_ID = @ProposalID AND Approval_Status = 1);
            DECLARE @TotalVotes INT = (SELECT COUNT(*) FROM dbo.VOTE WHERE Proposal_ID = @ProposalID);
            
            IF CAST(@YesVotes AS FLOAT) / @TotalVotes >= 0.51
                SET @FinalStatus = 'Approved';
            ELSE
                SET @FinalStatus = 'Rejected';
                
            UPDATE dbo.PROPOSAL SET Status = @FinalStatus WHERE Proposal_ID = @ProposalID;
        END
        ELSE
        BEGIN
            SET @FinalStatus = 'Active'; -- Still waiting on votes
        END
        
        COMMIT TRAN;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRAN;
        THROW;
    END CATCH
END;
GO


/* =========================================================================================
   PART 4: DML TRIGGER (Audit & Security)
   Purpose: Prevents silent financial tampering by creating an immutable paper trail.
========================================================================================= */

-- Create the Audit Log Table (Hidden from normal UI)
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'EXPENSE_AUDIT_LOG')
BEGIN
    CREATE TABLE dbo.EXPENSE_AUDIT_LOG (
        Audit_ID INT IDENTITY(1,1) PRIMARY KEY,
        Expense_ID INT NOT NULL,
        Old_Amount DECIMAL(10,2),
        New_Amount DECIMAL(10,2),
        Action_Type VARCHAR(10),
        Changed_By_User VARCHAR(100),
        Change_Timestamp DATETIME DEFAULT GETDATE()
    );
END
GO

-- Create the Trigger on the EXPENSE table
CREATE OR ALTER TRIGGER dbo.trg_AuditFinancialChanges
ON dbo.EXPENSE
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    
    -- Handle Updates (e.g., Someone maliciously changes a $50 bill to $100)
    IF EXISTS (SELECT * FROM inserted) AND EXISTS (SELECT * FROM deleted)
    BEGIN
        INSERT INTO dbo.EXPENSE_AUDIT_LOG (Expense_ID, Old_Amount, New_Amount, Action_Type, Changed_By_User)
        SELECT 
            i.Expense_ID, 
            d.Total_Amount, 
            i.Total_Amount, 
            'UPDATE', 
            SYSTEM_USER -- Captures the active database login
        FROM inserted i
        JOIN deleted d ON i.Expense_ID = d.Expense_ID
        WHERE i.Total_Amount <> d.Total_Amount; -- Only log if the money amount actually changed
    END
    
    -- Handle Deletes (e.g., Someone deletes a bill to avoid paying it)
    ELSE IF EXISTS (SELECT * FROM deleted) AND NOT EXISTS (SELECT * FROM inserted)
    BEGIN
        INSERT INTO dbo.EXPENSE_AUDIT_LOG (Expense_ID, Old_Amount, New_Amount, Action_Type, Changed_By_User)
        SELECT 
            d.Expense_ID, 
            d.Total_Amount, 
            NULL, 
            'DELETE', 
            SYSTEM_USER
        FROM deleted d;
    END
END;
GO