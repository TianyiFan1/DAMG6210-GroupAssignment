-- REMOVED FOR AZURE: USE CoHabitant;
-- REMOVED FOR AZURE: GO

/* =========================================================================================
   PART 1: VIEWS (The DataFrames for Streamlit & Power BI)
   
   All views filter on Is_Active = 1 to exclude soft-deleted records.
========================================================================================= */

-- View 1: Financial Ledger Dashboard
CREATE OR ALTER VIEW dbo.vw_App_Ledger_ActiveBalances AS
SELECT 
    t.Tenant_ID,
    p.First_Name + ' ' + p.Last_Name AS Full_Name,
    t.Current_Net_Balance,
    ISNULL(SUM(es.Owed_Amount), 0) AS Total_Pending_Debts,
    (SELECT ISNULL(SUM(Amount), 0) FROM dbo.PAYMENT WHERE Payer_Tenant_ID = t.Tenant_ID AND Is_Active = 1) 
    + ISNULL((SELECT SUM(Total_Amount) FROM dbo.EXPENSE WHERE Paid_By_Tenant_ID = t.Tenant_ID AND Is_Active = 1), 0)
    AS Lifetime_Paid
FROM dbo.TENANT t
JOIN dbo.PERSON p ON t.Tenant_ID = p.Person_ID
LEFT JOIN dbo.EXPENSE_SHARE es ON t.Tenant_ID = es.Owed_By_Tenant_ID AND es.Status = 'Pending' AND es.Is_Active = 1
WHERE t.Is_Active = 1 AND p.Is_Active = 1
GROUP BY t.Tenant_ID, p.First_Name, p.Last_Name, t.Current_Net_Balance;
GO

-- View 2: Chore Leaderboard & Gamification
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
LEFT JOIN dbo.CHORE_ASSIGNMENT ca ON t.Tenant_ID = ca.Assigned_Tenant_ID AND ca.Is_Active = 1
WHERE t.Is_Active = 1 AND p.Is_Active = 1
GROUP BY t.Tenant_ID, p.First_Name, t.Tenant_Responsibility_Score;
GO

-- View 3: Utility Time-Series
CREATE OR ALTER VIEW dbo.vw_App_Utility_TimeSeries AS
SELECT 
    ur.Reading_Date,
    ut.Type_Name AS Utility_Category,
    ur.Provider_Name,
    ur.Meter_Value AS Cost_Amount,
    p.Street_Address
FROM dbo.UTILITY_READING ur
JOIN dbo.UTILITY_TYPE ut ON ur.Utility_Type_ID = ut.Utility_Type_ID
JOIN dbo.PROPERTY p ON ur.Property_ID = p.Property_ID
WHERE ur.Is_Active = 1 AND p.Is_Active = 1;
GO


/* =========================================================================================
   PART 2: USER-DEFINED FUNCTIONS (UDFs)
========================================================================================= */

-- UDF 1 (Scalar): Calculate exact split amount scoped to a single property
CREATE OR ALTER FUNCTION dbo.fn_CalculateExpenseShare (
    @TotalAmount DECIMAL(10,2),
    @Property_ID INT
)
RETURNS DECIMAL(10,2)
AS
BEGIN
    DECLARE @ActiveTenants INT;
    DECLARE @Share DECIMAL(10,2);
    
    SELECT @ActiveTenants = COUNT(DISTINCT la.Tenant_ID) 
    FROM dbo.LEASE_AGREEMENT la
    WHERE la.Property_ID = @Property_ID
      AND la.Is_Active = 1
      AND la.Start_Date <= CAST(GETDATE() AS DATE) 
      AND la.End_Date >= CAST(GETDATE() AS DATE);
      
    IF @ActiveTenants = 0 SET @ActiveTenants = 1;
    
    SET @Share = @TotalAmount / @ActiveTenants;
    RETURN @Share;
END;
GO

-- UDF 2 (Scalar): Get Remaining Votes Needed for a Proposal
CREATE OR ALTER FUNCTION dbo.fn_GetPendingVoteCount (@Proposal_ID INT)
RETURNS INT
AS
BEGIN
    DECLARE @ProposalPropertyID INT;
    DECLARE @TotalEligibleTenants INT;
    DECLARE @VotesCast INT;

    SELECT TOP 1
        @ProposalPropertyID = la.Property_ID
    FROM dbo.PROPOSAL p
    INNER JOIN dbo.LEASE_AGREEMENT la ON la.Tenant_ID = p.Proposed_By_Tenant_ID
    WHERE p.Proposal_ID = @Proposal_ID
        AND p.Is_Active = 1
        AND la.Is_Active = 1
        AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
    ORDER BY la.End_Date DESC, la.Lease_ID DESC;

    IF @ProposalPropertyID IS NULL
        RETURN 0;

    SELECT @TotalEligibleTenants = COUNT(DISTINCT la.Tenant_ID)
    FROM dbo.LEASE_AGREEMENT la
    WHERE la.Property_ID = @ProposalPropertyID
        AND la.Is_Active = 1
        AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date;

    SELECT @VotesCast = COUNT(DISTINCT v.Tenant_ID)
    FROM dbo.VOTE v
    INNER JOIN dbo.LEASE_AGREEMENT la ON la.Tenant_ID = v.Tenant_ID
    WHERE v.Proposal_ID = @Proposal_ID
        AND v.Is_Active = 1
        AND la.Property_ID = @ProposalPropertyID
        AND la.Is_Active = 1
        AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date;

    IF @TotalEligibleTenants < @VotesCast
        SET @VotesCast = @TotalEligibleTenants;

    RETURN (@TotalEligibleTenants - @VotesCast);
END;
GO

-- UDF 3 (Table-Valued): Point-in-Time House Roster
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
      AND la.Is_Active = 1
      AND t.Is_Active = 1
);
GO


/* =========================================================================================
   PART 3: STORED PROCEDURES (The Backend API Layer)
   
   All CATCH blocks INSERT into dbo.SYSTEM_ERROR_LOG before re-throwing.
========================================================================================= */

-- SP 1: Create an Expense and Auto-Split it
CREATE OR ALTER PROCEDURE dbo.usp_CreateHouseholdExpense
    @PaidByTenantID INT,
    @Amount DECIMAL(10,2),
    @SplitPolicy VARCHAR(50),
    @ReceiptURL VARCHAR(255),
    @NewExpenseID INT OUTPUT
AS
BEGIN
    SET XACT_ABORT ON; 
    BEGIN TRY
        BEGIN TRAN;
        
        DECLARE @PayerPropertyID INT;
        SELECT TOP 1 @PayerPropertyID = la.Property_ID
        FROM dbo.LEASE_AGREEMENT la
        WHERE la.Tenant_ID = @PaidByTenantID
          AND la.Is_Active = 1
          AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
        ORDER BY la.End_Date DESC, la.Lease_ID DESC;

        IF @PayerPropertyID IS NULL
            THROW 51004, 'Payer does not have an active lease. Cannot create expense.', 1;

        INSERT INTO dbo.EXPENSE (Paid_By_Tenant_ID, Total_Amount, Date_Incurred, Split_Policy, Receipt_Image)
        VALUES (@PaidByTenantID, @Amount, CAST(GETDATE() AS DATE), @SplitPolicy, @ReceiptURL);
        
        SET @NewExpenseID = SCOPE_IDENTITY();
        
        DECLARE @CalculatedShare DECIMAL(10,2) = dbo.fn_CalculateExpenseShare(@Amount, @PayerPropertyID);
        
        INSERT INTO dbo.EXPENSE_SHARE (Expense_ID, Owed_By_Tenant_ID, Owed_Amount, Status)
        SELECT @NewExpenseID, la.Tenant_ID, @CalculatedShare, 'Pending'
        FROM dbo.LEASE_AGREEMENT la
        WHERE la.Property_ID = @PayerPropertyID
          AND la.Is_Active = 1
          AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
          AND la.Tenant_ID <> @PaidByTenantID;
        
        COMMIT TRAN;
        RETURN 0; 
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRAN;
        INSERT INTO dbo.SYSTEM_ERROR_LOG (
            Error_Message, Error_Severity, Error_State,
            Error_Procedure, Error_Line, Tenant_ID, Additional_Context
        ) VALUES (
            ERROR_MESSAGE(), ERROR_SEVERITY(), ERROR_STATE(),
            ERROR_PROCEDURE(), ERROR_LINE(), @PaidByTenantID,
            CONCAT('Amount=', @Amount, ' SplitPolicy=', @SplitPolicy)
        );
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
    @NewBalance DECIMAL(10,2) OUTPUT,
    @PayeeTenantID INT = NULL
AS
BEGIN
    SET XACT_ABORT ON;
    BEGIN TRY
        BEGIN TRAN;

        IF @Amount IS NULL OR @Amount <= 0
            THROW 51003, 'Payment amount must be greater than zero.', 1;
        
        IF @PayeeTenantID IS NULL
            SET @PayeeTenantID = @PayerTenantID;
        
        INSERT INTO dbo.PAYMENT (Payer_Tenant_ID, Payee_Tenant_ID, Amount, Payment_Date, Note, Payment_Type)
        VALUES (@PayerTenantID, @PayeeTenantID, @Amount, CAST(GETDATE() AS DATE), @Note, 'Payment');
        
        UPDATE dbo.TENANT
        SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) + @Amount
        WHERE Tenant_ID = @PayerTenantID;
        
        SELECT @NewBalance = Current_Net_Balance FROM dbo.TENANT WHERE Tenant_ID = @PayerTenantID;
        
        COMMIT TRAN;
        RETURN 0;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRAN;
        INSERT INTO dbo.SYSTEM_ERROR_LOG (
            Error_Message, Error_Severity, Error_State,
            Error_Procedure, Error_Line, Tenant_ID, Additional_Context
        ) VALUES (
            ERROR_MESSAGE(), ERROR_SEVERITY(), ERROR_STATE(),
            ERROR_PROCEDURE(), ERROR_LINE(), @PayerTenantID,
            CONCAT('Amount=', @Amount, ' PayeeTenantID=', ISNULL(@PayeeTenantID, -1))
        );
        THROW;
    END CATCH
END;
GO

-- SP 3: Securely Cast a Vote and Auto-Resolve the Proposal
CREATE OR ALTER PROCEDURE dbo.usp_CastProposalVote
    @ProposalID INT,
    @TenantID INT,
    @IsApproved BIT,
    @FinalStatus VARCHAR(20) OUTPUT
AS
BEGIN
    SET XACT_ABORT ON;
    BEGIN TRY
        BEGIN TRAN;

        DECLARE @ProposalPropertyID INT;
        DECLARE @VoterPropertyID INT;

        SELECT TOP 1
            @ProposalPropertyID = la.Property_ID
        FROM dbo.PROPOSAL p
        INNER JOIN dbo.LEASE_AGREEMENT la ON la.Tenant_ID = p.Proposed_By_Tenant_ID
        WHERE p.Proposal_ID = @ProposalID
          AND p.Status = 'Active'
          AND p.Is_Active = 1
          AND la.Is_Active = 1
          AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
        ORDER BY la.End_Date DESC, la.Lease_ID DESC;

        IF @ProposalPropertyID IS NULL
            THROW 51001, 'Proposal is not active or proposer is not on an active lease.', 1;

        SELECT TOP 1
            @VoterPropertyID = la.Property_ID
        FROM dbo.LEASE_AGREEMENT la
        WHERE la.Tenant_ID = @TenantID
          AND la.Is_Active = 1
          AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
        ORDER BY la.End_Date DESC, la.Lease_ID DESC;

        IF @VoterPropertyID IS NULL OR @VoterPropertyID <> @ProposalPropertyID
            THROW 51002, 'Tenant is not eligible to vote on this proposal.', 1;
        
        INSERT INTO dbo.VOTE (Proposal_ID, Tenant_ID, Approval_Status, Vote_Timestamp)
        VALUES (@ProposalID, @TenantID, @IsApproved, GETDATE());
        
        IF dbo.fn_GetPendingVoteCount(@ProposalID) = 0
        BEGIN
            DECLARE @YesVotes INT = (SELECT COUNT(*) FROM dbo.VOTE WHERE Proposal_ID = @ProposalID AND Approval_Status = 1 AND Is_Active = 1);
            DECLARE @TotalVotes INT = (SELECT COUNT(*) FROM dbo.VOTE WHERE Proposal_ID = @ProposalID AND Is_Active = 1);
            
            IF CAST(@YesVotes AS FLOAT) / @TotalVotes >= 0.51
                SET @FinalStatus = 'Approved';
            ELSE
                SET @FinalStatus = 'Rejected';
                
            UPDATE dbo.PROPOSAL SET Status = @FinalStatus WHERE Proposal_ID = @ProposalID;
        END
        ELSE
        BEGIN
            SET @FinalStatus = 'Active';
        END
        
        COMMIT TRAN;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRAN;
        INSERT INTO dbo.SYSTEM_ERROR_LOG (
            Error_Message, Error_Severity, Error_State,
            Error_Procedure, Error_Line, Tenant_ID, Additional_Context
        ) VALUES (
            ERROR_MESSAGE(), ERROR_SEVERITY(), ERROR_STATE(),
            ERROR_PROCEDURE(), ERROR_LINE(), @TenantID,
            CONCAT('ProposalID=', @ProposalID, ' IsApproved=', @IsApproved)
        );
        THROW;
    END CATCH
END;
GO


/* =========================================================================================
   SP 4: Settle Peer Debt (Audit Finding — Race Condition Fix)
   
   Moves ALL settlement math out of the Streamlit UI and into a strict
   transactional SP with UPDLOCK hints to prevent two users from
   over-settling the same debt simultaneously.
   
   Steps (atomic):
     1. Validate both tenants are on the same active property
     2. Acquire UPDLOCK on both TENANT rows (serializes concurrent settles)
     3. Compute real-time outstanding debt between the pair from EXPENSE_SHARE
     4. Validate settlement amount does not exceed the outstanding balance
     5. Insert PAYMENT record (type = 'Settlement')
     6. Update both TENANT.Current_Net_Balance
     7. Mark EXPENSE_SHARE rows from 'Pending' → 'Paid' (FIFO by Share_ID)
        up to the settlement amount
========================================================================================= */

CREATE OR ALTER PROCEDURE dbo.usp_SettlePeerDebt
    @CallerTenantID INT,          -- The logged-in user initiating the settlement
    @CounterpartyTenantID INT,    -- The other roommate
    @SettleAmount DECIMAL(10,2),  -- How much to settle
    @Note VARCHAR(255) = NULL
AS
BEGIN
    SET XACT_ABORT ON;
    BEGIN TRY
        BEGIN TRAN;

        -- ── Guard: positive amount ──
        IF @SettleAmount IS NULL OR @SettleAmount <= 0
            THROW 51010, 'Settlement amount must be greater than zero.', 1;

        IF @CallerTenantID = @CounterpartyTenantID
            THROW 51011, 'Cannot settle a debt with yourself.', 1;

        -- ── Guard: same property ──
        DECLARE @CallerPropID INT, @CounterPropID INT;

        SELECT TOP 1 @CallerPropID = la.Property_ID
        FROM dbo.LEASE_AGREEMENT la
        WHERE la.Tenant_ID = @CallerTenantID AND la.Is_Active = 1
          AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
        ORDER BY la.End_Date DESC;

        SELECT TOP 1 @CounterPropID = la.Property_ID
        FROM dbo.LEASE_AGREEMENT la
        WHERE la.Tenant_ID = @CounterpartyTenantID AND la.Is_Active = 1
          AND CAST(GETDATE() AS DATE) BETWEEN la.Start_Date AND la.End_Date
        ORDER BY la.End_Date DESC;

        IF @CallerPropID IS NULL OR @CounterPropID IS NULL OR @CallerPropID <> @CounterPropID
            THROW 51012, 'Both tenants must be on the same active property to settle.', 1;

        -- ── Acquire UPDLOCK on both tenant rows in deterministic order ──
        -- Re-audit fix (Finding #3): The original code locked rows in
        -- caller/counterparty parameter order.  Two concurrent sessions
        -- settling each other (A→B and B→A) would acquire locks in
        -- opposite order, causing a deadlock.  Fix: always lock the
        -- lower Tenant_ID first, guaranteeing a consistent global lock
        -- order that breaks the circular-wait condition.
        DECLARE @LowID INT  = CASE WHEN @CallerTenantID < @CounterpartyTenantID
                                   THEN @CallerTenantID ELSE @CounterpartyTenantID END;
        DECLARE @HighID INT = CASE WHEN @CallerTenantID < @CounterpartyTenantID
                                   THEN @CounterpartyTenantID ELSE @CallerTenantID END;

        DECLARE @CallerBalance DECIMAL(10,2), @CounterBalance DECIMAL(10,2);
        DECLARE @LowBalance DECIMAL(10,2), @HighBalance DECIMAL(10,2);

        -- Lock #1: lower Tenant_ID
        SELECT @LowBalance = Current_Net_Balance
        FROM dbo.TENANT WITH (UPDLOCK, ROWLOCK)
        WHERE Tenant_ID = @LowID;

        -- Lock #2: higher Tenant_ID (never reversed by any concurrent session)
        SELECT @HighBalance = Current_Net_Balance
        FROM dbo.TENANT WITH (UPDLOCK, ROWLOCK)
        WHERE Tenant_ID = @HighID;

        -- Map back to caller/counterparty variables for downstream logic
        SET @CallerBalance  = CASE WHEN @CallerTenantID = @LowID THEN @LowBalance ELSE @HighBalance END;
        SET @CounterBalance = CASE WHEN @CounterpartyTenantID = @LowID THEN @LowBalance ELSE @HighBalance END;

        -- ── Compute real-time pending debt between the pair ──
        -- CallerOwesCounter: sum of pending shares where caller owes the counterparty
        DECLARE @CallerOwesCounter DECIMAL(10,2) = ISNULL((
            SELECT SUM(es.Owed_Amount)
            FROM dbo.EXPENSE_SHARE es
            JOIN dbo.EXPENSE e ON e.Expense_ID = es.Expense_ID
            WHERE es.Owed_By_Tenant_ID = @CallerTenantID
              AND e.Paid_By_Tenant_ID = @CounterpartyTenantID
              AND es.Status = 'Pending' AND es.Is_Active = 1 AND e.Is_Active = 1
        ), 0);

        -- CounterOwesCaller: sum of pending shares where counterparty owes the caller
        DECLARE @CounterOwesCaller DECIMAL(10,2) = ISNULL((
            SELECT SUM(es.Owed_Amount)
            FROM dbo.EXPENSE_SHARE es
            JOIN dbo.EXPENSE e ON e.Expense_ID = es.Expense_ID
            WHERE es.Owed_By_Tenant_ID = @CounterpartyTenantID
              AND e.Paid_By_Tenant_ID = @CallerTenantID
              AND es.Status = 'Pending' AND es.Is_Active = 1 AND e.Is_Active = 1
        ), 0);

        -- Determine net direction: who actually pays whom
        DECLARE @PayerTenantID INT, @PayeeTenantID INT, @MaxSettleable DECIMAL(10,2);

        IF @CallerOwesCounter >= @CounterOwesCaller
        BEGIN
            -- Caller is the net debtor → Caller pays Counterparty
            SET @PayerTenantID  = @CallerTenantID;
            SET @PayeeTenantID  = @CounterpartyTenantID;
            SET @MaxSettleable  = @CallerOwesCounter - @CounterOwesCaller;
        END
        ELSE
        BEGIN
            -- Counterparty is the net debtor → Counterparty pays Caller
            SET @PayerTenantID  = @CounterpartyTenantID;
            SET @PayeeTenantID  = @CallerTenantID;
            SET @MaxSettleable  = @CounterOwesCaller - @CallerOwesCounter;
        END

        IF @MaxSettleable <= 0
            THROW 51013, 'No outstanding debt exists between these tenants.', 1;

        IF @SettleAmount > @MaxSettleable
            THROW 51014, 'Settlement amount exceeds outstanding balance between these tenants.', 1;

        -- ── Step 1: Insert settlement payment record ──
        INSERT INTO dbo.PAYMENT (Payer_Tenant_ID, Payee_Tenant_ID, Amount, Payment_Type, Payment_Date, Note)
        VALUES (@PayerTenantID, @PayeeTenantID, @SettleAmount, 'Settlement',
                CAST(GETDATE() AS DATE), ISNULL(@Note, 'Peer debt settlement'));

        -- ── Step 2: Update both TENANT balances ──
        UPDATE dbo.TENANT
        SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) + @SettleAmount
        WHERE Tenant_ID = @PayerTenantID;

        UPDATE dbo.TENANT
        SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) - @SettleAmount
        WHERE Tenant_ID = @PayeeTenantID;

        -- ── Step 3: Mark EXPENSE_SHARE rows Pending → Paid (FIFO by Share_ID) ──
        -- Walk through the payer's pending shares owed to the payee in order,
        -- flipping them to 'Paid' until we've consumed the settlement amount.
        DECLARE @Remaining DECIMAL(10,2) = @SettleAmount;
        DECLARE @CurShareID INT, @CurOwed DECIMAL(10,2);

        DECLARE share_cursor CURSOR LOCAL FAST_FORWARD FOR
            SELECT es.Share_ID, es.Owed_Amount
            FROM dbo.EXPENSE_SHARE es
            JOIN dbo.EXPENSE e ON e.Expense_ID = es.Expense_ID
            WHERE es.Owed_By_Tenant_ID = @PayerTenantID
              AND e.Paid_By_Tenant_ID = @PayeeTenantID
              AND es.Status = 'Pending'
              AND es.Is_Active = 1 AND e.Is_Active = 1
            ORDER BY es.Share_ID ASC;  -- FIFO

        OPEN share_cursor;
        FETCH NEXT FROM share_cursor INTO @CurShareID, @CurOwed;

        WHILE @@FETCH_STATUS = 0 AND @Remaining > 0
        BEGIN
            IF @CurOwed <= @Remaining
            BEGIN
                -- Fully covers this share → mark Paid
                UPDATE dbo.EXPENSE_SHARE SET Status = 'Paid' WHERE Share_ID = @CurShareID;
                SET @Remaining = @Remaining - @CurOwed;
            END
            ELSE
            BEGIN
                -- Partial: settlement doesn't fully cover this share.
                -- Reduce the Owed_Amount by the remaining settlement so future
                -- debt calculations see the true residual, not the original face
                -- value.  Status stays 'Pending' (only fully covered shares flip
                -- to 'Paid').  Without this reduction, the next settlement call
                -- would recompute outstanding debt from the unreduced Owed_Amount
                -- and allow over-settlement.
                UPDATE dbo.EXPENSE_SHARE
                SET Owed_Amount = Owed_Amount - @Remaining
                WHERE Share_ID = @CurShareID;

                SET @Remaining = 0;
            END

            FETCH NEXT FROM share_cursor INTO @CurShareID, @CurOwed;
        END

        CLOSE share_cursor;
        DEALLOCATE share_cursor;

        COMMIT TRAN;

        -- Return the payer/payee info for the UI
        SELECT @PayerTenantID AS PayerTenantID,
               @PayeeTenantID AS PayeeTenantID,
               @SettleAmount AS SettledAmount,
               @MaxSettleable AS MaxWas;

        RETURN 0;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRAN;
        INSERT INTO dbo.SYSTEM_ERROR_LOG (
            Error_Message, Error_Severity, Error_State,
            Error_Procedure, Error_Line, Tenant_ID, Additional_Context
        ) VALUES (
            ERROR_MESSAGE(), ERROR_SEVERITY(), ERROR_STATE(),
            ERROR_PROCEDURE(), ERROR_LINE(), @CallerTenantID,
            CONCAT('CounterpartyID=', @CounterpartyTenantID, ' Amount=', @SettleAmount)
        );
        THROW;
    END CATCH
END;
GO


/* =========================================================================================
   SP 5: Soft-Delete Expense (Audit Finding — Centralize Financial Mutations)
   
   Moves the ad-hoc soft-delete SQL out of the Streamlit UI into a proper SP
   protected by SYSTEM_ERROR_LOG CATCH blocks.
   
   Re-audit fix (Finding #2): The original version refunded ALL active shares
   regardless of Status.  If part of an expense was already settled (Status =
   'Paid'), the debtor had already transferred money via a settlement PAYMENT.
   Refunding the full Owed_Amount of a Paid share would double-reverse the
   economics.  The fix:
     a) Guard: block deletion if any share is already 'Paid' (you cannot
        retroactively undo an expense that roommates have already settled
        without also reversing the settlement — a much more complex op).
     b) Defense-in-depth: refund queries now filter on Status = 'Pending'
        so even if the guard is bypassed, only unsettled amounts move.
   
   Steps (atomic):
     1. Ownership guard
     2. Settlement-safety guard (block if any share is Paid)
     3. Refund each PENDING debtor's balance
     4. Debit the payer's balance (only Pending share sum)
     5. Soft-delete EXPENSE_SHARE rows (Is_Active = 0)
     6. Soft-delete EXPENSE row (Is_Active = 0, captured by temporal history)
========================================================================================= */

CREATE OR ALTER PROCEDURE dbo.usp_SoftDeleteExpense
    @ExpenseID INT,
    @CallerTenantID INT
AS
BEGIN
    SET XACT_ABORT ON;
    BEGIN TRY
        BEGIN TRAN;

        -- ── Guard 1: expense must exist, be active, and belong to the caller ──
        IF NOT EXISTS (
            SELECT 1 FROM dbo.EXPENSE
            WHERE Expense_ID = @ExpenseID
              AND Paid_By_Tenant_ID = @CallerTenantID
              AND Is_Active = 1
        )
            THROW 51020, 'Unauthorized, already deleted, or Expense not found.', 1;

        -- ── Guard 2: block if any share has already been settled ──
        -- Reversing a settled share would require also reversing the
        -- corresponding settlement PAYMENT, which is a separate operation.
        -- Blocking here is the safe, conservative choice.
        IF EXISTS (
            SELECT 1 FROM dbo.EXPENSE_SHARE
            WHERE Expense_ID = @ExpenseID
              AND Is_Active = 1
              AND Status = 'Paid'
        )
            THROW 51021, 'Cannot delete an expense that has settled shares. Reverse the settlement first.', 1;

        -- ── Step 1: Refund each PENDING debtor (reverse their balance deduction) ──
        -- Defense-in-depth: only Pending shares are refunded even though
        -- Guard 2 should have blocked any Paid shares above.
        UPDATE t
        SET t.Current_Net_Balance = ISNULL(t.Current_Net_Balance, 0) + es.Owed_Amount
        FROM dbo.TENANT t
        INNER JOIN dbo.EXPENSE_SHARE es ON t.Tenant_ID = es.Owed_By_Tenant_ID
        WHERE es.Expense_ID = @ExpenseID
          AND es.Is_Active = 1
          AND es.Status = 'Pending';

        -- ── Step 2: Debit the payer (reverse only the Pending share sum) ──
        UPDATE dbo.TENANT
        SET Current_Net_Balance = ISNULL(Current_Net_Balance, 0) - ISNULL((
            SELECT SUM(es2.Owed_Amount)
            FROM dbo.EXPENSE_SHARE es2
            WHERE es2.Expense_ID = @ExpenseID
              AND es2.Is_Active = 1
              AND es2.Status = 'Pending'
        ), 0)
        WHERE Tenant_ID = @CallerTenantID;

        -- ── Step 3: Soft-delete share records ──
        UPDATE dbo.EXPENSE_SHARE
        SET Is_Active = 0
        WHERE Expense_ID = @ExpenseID;

        -- ── Step 4: Soft-delete expense (temporal history captures this) ──
        UPDATE dbo.EXPENSE
        SET Is_Active = 0
        WHERE Expense_ID = @ExpenseID;

        COMMIT TRAN;
        RETURN 0;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT > 0 ROLLBACK TRAN;
        INSERT INTO dbo.SYSTEM_ERROR_LOG (
            Error_Message, Error_Severity, Error_State,
            Error_Procedure, Error_Line, Tenant_ID, Additional_Context
        ) VALUES (
            ERROR_MESSAGE(), ERROR_SEVERITY(), ERROR_STATE(),
            ERROR_PROCEDURE(), ERROR_LINE(), @CallerTenantID,
            CONCAT('ExpenseID=', @ExpenseID)
        );
        THROW;
    END CATCH
END;
GO


/* =========================================================================================
   PART 4: DML TRIGGER (Audit — Legacy)
   
   Retained as a secondary audit trail alongside temporal tables.
========================================================================================= */

CREATE OR ALTER TRIGGER dbo.trg_AuditFinancialChanges
ON dbo.EXPENSE
AFTER UPDATE, DELETE
AS
BEGIN
    SET NOCOUNT ON;
    
    IF EXISTS (SELECT * FROM inserted) AND EXISTS (SELECT * FROM deleted)
    BEGIN
        INSERT INTO dbo.EXPENSE_AUDIT_LOG (Expense_ID, Old_Amount, New_Amount, Action_Type, Changed_By_User)
        SELECT 
            i.Expense_ID, 
            d.Total_Amount, 
            i.Total_Amount, 
            'UPDATE', 
            SYSTEM_USER
        FROM inserted i
        JOIN deleted d ON i.Expense_ID = d.Expense_ID
        WHERE i.Total_Amount <> d.Total_Amount;
    END
    
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
