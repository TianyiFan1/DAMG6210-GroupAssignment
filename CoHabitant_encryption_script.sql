USE CoHabitant;
GO

IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = '##MS_DatabaseMasterKey##')
BEGIN
    CREATE MASTER KEY ENCRYPTION BY PASSWORD = 'CoHabitant_StrongPassword123!';
END
GO

IF NOT EXISTS (SELECT * FROM sys.certificates WHERE name = 'CoHabitant_Cert')
BEGIN
    CREATE CERTIFICATE CoHabitant_Cert WITH SUBJECT = 'CoHabitant PII Protection';
END
GO

IF NOT EXISTS (SELECT * FROM sys.symmetric_keys WHERE name = 'CoHabitant_SymKey')
BEGIN
    CREATE SYMMETRIC KEY CoHabitant_SymKey WITH ALGORITHM = AES_256 ENCRYPTION BY CERTIFICATE CoHabitant_Cert;
END
GO

IF COL_LENGTH('dbo.LANDLORD', 'Bank_Details_Encrypted') IS NULL
BEGIN
    ALTER TABLE dbo.LANDLORD ADD Bank_Details_Encrypted VARBINARY(MAX);
    ALTER TABLE dbo.LANDLORD ADD Tax_ID_Encrypted VARBINARY(MAX);
END
GO

-- Only attempt to encrypt and drop if the old columns still exist!
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