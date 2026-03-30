-- ============================================================================
-- CoHabitant — Azure SQL Encryption (Step 5 of 5) — Combined Runner
-- ============================================================================
-- This file sets the session context AND runs encryption in one execution.
-- Just open this file and hit Ctrl+Shift+E — no separate steps needed.
-- ============================================================================

-- Step A: Set the master key password in the session context
EXEC sp_set_session_context 'DB_MASTER_KEY_PASSWORD', 'CoHabitant_Azure_2026!';
GO

-- Step B: Create master key (if not exists)
IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
BEGIN
    DECLARE @MasterKeyPassword NVARCHAR(4000) = CAST(SESSION_CONTEXT(N'DB_MASTER_KEY_PASSWORD') AS NVARCHAR(4000));
    IF @MasterKeyPassword IS NULL OR LEN(@MasterKeyPassword) < 16
        THROW 50010, 'Missing/weak DB master key password.', 1;

    DECLARE @CreateMasterKeySql NVARCHAR(MAX) =
        N'CREATE MASTER KEY ENCRYPTION BY PASSWORD = ''' + REPLACE(@MasterKeyPassword, '''', '''''') + N''';';
    EXEC sp_executesql @CreateMasterKeySql;
END
GO

-- Step C: Create certificate (if not exists)
IF NOT EXISTS (SELECT * FROM sys.certificates WHERE name = 'CoHabitant_Cert')
BEGIN
    CREATE CERTIFICATE CoHabitant_Cert WITH SUBJECT = 'CoHabitant PII Protection';
END
GO

-- Step D: Create symmetric key (if not exists)
IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = 'CoHabitant_SymKey')
BEGIN
    CREATE SYMMETRIC KEY CoHabitant_SymKey WITH ALGORITHM = AES_256 ENCRYPTION BY CERTIFICATE CoHabitant_Cert;
END
GO

-- Step E: Add encrypted columns (if not exists)
IF COL_LENGTH('dbo.LANDLORD', 'Bank_Details_Encrypted') IS NULL
BEGIN
    ALTER TABLE dbo.LANDLORD ADD Bank_Details_Encrypted VARBINARY(MAX);
    ALTER TABLE dbo.LANDLORD ADD Tax_ID_Encrypted VARBINARY(MAX);
END
GO

-- Step F: Encrypt existing data and drop plaintext columns
IF COL_LENGTH('dbo.LANDLORD', 'Bank_Details') IS NOT NULL
BEGIN
    OPEN SYMMETRIC KEY CoHabitant_SymKey DECRYPTION BY CERTIFICATE CoHabitant_Cert;

    UPDATE dbo.LANDLORD
    SET 
        Bank_Details_Encrypted = ENCRYPTBYKEY(KEY_GUID('CoHabitant_SymKey'), Bank_Details),
        Tax_ID_Encrypted = ENCRYPTBYKEY(KEY_GUID('CoHabitant_SymKey'), Tax_ID)
    WHERE Bank_Details IS NOT NULL OR Tax_ID IS NOT NULL;

    CLOSE SYMMETRIC KEY CoHabitant_SymKey;

    ALTER TABLE dbo.LANDLORD DROP COLUMN Bank_Details;
    ALTER TABLE dbo.LANDLORD DROP COLUMN Tax_ID;
END
GO
