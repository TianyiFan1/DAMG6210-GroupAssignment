-- 1. CREATE DATABASE
IF NOT EXISTS (SELECT * FROM sys.databases WHERE name = 'CoHabitant')
BEGIN
    CREATE DATABASE CoHabitant;
END
GO

USE CoHabitant;
GO

-- 2. DROP TABLES (Strict Reverse Dependency Order)

-- SEVER CIRCULAR DEPENDENCIES FIRST: 
IF OBJECT_ID('dbo.FK_Tenant_Lease', 'F') IS NOT NULL 
    ALTER TABLE dbo.TENANT DROP CONSTRAINT FK_Tenant_Lease;
IF OBJECT_ID('dbo.FK_Lease_Tenant', 'F') IS NOT NULL 
    ALTER TABLE dbo.LEASE_AGREEMENT DROP CONSTRAINT FK_Lease_Tenant;

IF OBJECT_ID('dbo.VOTE', 'U') IS NOT NULL DROP TABLE dbo.VOTE;
IF OBJECT_ID('dbo.PROPOSAL', 'U') IS NOT NULL DROP TABLE dbo.PROPOSAL;
IF OBJECT_ID('dbo.CHORE_ASSIGNMENT', 'U') IS NOT NULL DROP TABLE dbo.CHORE_ASSIGNMENT;
IF OBJECT_ID('dbo.CHORE_DEFINITION', 'U') IS NOT NULL DROP TABLE dbo.CHORE_DEFINITION;
IF OBJECT_ID('dbo.PAYMENT', 'U') IS NOT NULL DROP TABLE dbo.PAYMENT;
IF OBJECT_ID('dbo.EXPENSE_SHARE', 'U') IS NOT NULL DROP TABLE dbo.EXPENSE_SHARE;
IF OBJECT_ID('dbo.EXPENSE', 'U') IS NOT NULL DROP TABLE dbo.EXPENSE;
IF OBJECT_ID('dbo.PERSONAL_ITEM', 'U') IS NOT NULL DROP TABLE dbo.PERSONAL_ITEM;
IF OBJECT_ID('dbo.SHARED_ITEM', 'U') IS NOT NULL DROP TABLE dbo.SHARED_ITEM;
IF OBJECT_ID('dbo.INVENTORY_ITEM', 'U') IS NOT NULL DROP TABLE dbo.INVENTORY_ITEM;
IF OBJECT_ID('dbo.GUEST', 'U') IS NOT NULL DROP TABLE dbo.GUEST;
IF OBJECT_ID('dbo.SUB_LEASE', 'U') IS NOT NULL DROP TABLE dbo.SUB_LEASE;
IF OBJECT_ID('dbo.UTILITY_READING', 'U') IS NOT NULL DROP TABLE dbo.UTILITY_READING;
IF OBJECT_ID('dbo.UTILITY_TYPE', 'U') IS NOT NULL DROP TABLE dbo.UTILITY_TYPE;
IF OBJECT_ID('dbo.LEASE_AGREEMENT', 'U') IS NOT NULL DROP TABLE dbo.LEASE_AGREEMENT;
IF OBJECT_ID('dbo.TENANT', 'U') IS NOT NULL DROP TABLE dbo.TENANT;
IF OBJECT_ID('dbo.PROPERTY', 'U') IS NOT NULL DROP TABLE dbo.PROPERTY;
IF OBJECT_ID('dbo.LANDLORD', 'U') IS NOT NULL DROP TABLE dbo.LANDLORD;
IF OBJECT_ID('dbo.PERSON', 'U') IS NOT NULL DROP TABLE dbo.PERSON;
GO

-- 3. CREATE TABLES

-- [A. User Management]
CREATE TABLE dbo.PERSON (
    Person_ID INT IDENTITY(1,1) PRIMARY KEY,
    First_Name VARCHAR(50) NOT NULL,
    Last_Name VARCHAR(50) NOT NULL,
    Email VARCHAR(100) NOT NULL UNIQUE,
    Phone_Number VARCHAR(20)
);

CREATE TABLE dbo.LANDLORD (
    Landlord_ID INT PRIMARY KEY,
    Bank_Details VARCHAR(255),
    Tax_ID VARCHAR(50),
    CONSTRAINT FK_Landlord_Person FOREIGN KEY (Landlord_ID) REFERENCES dbo.PERSON(Person_ID)
);

-- [B. Property & Occupancy]
CREATE TABLE dbo.PROPERTY (
    Property_ID INT IDENTITY(1,1) PRIMARY KEY,
    Landlord_ID INT,
    Street_Address VARCHAR(150) NOT NULL,
    City VARCHAR(50) NOT NULL,
    State VARCHAR(50) NOT NULL,
    Zip_Code VARCHAR(20) NOT NULL,
    Max_Occupancy INT,
    WiFi_Password VARCHAR(50),
    CONSTRAINT FK_Property_Landlord FOREIGN KEY (Landlord_ID) REFERENCES dbo.LANDLORD(Landlord_ID),
    CONSTRAINT CHK_Property_MaxOcc CHECK (Max_Occupancy > 0)
);

CREATE TABLE dbo.TENANT (
    Tenant_ID INT PRIMARY KEY,
    Current_Net_Balance DECIMAL(10,2) DEFAULT 0.00,
    Emergency_Contact VARCHAR(100),
    Tenant_Responsibility_Score INT DEFAULT 100,
    CONSTRAINT FK_Tenant_Person FOREIGN KEY (Tenant_ID) REFERENCES dbo.PERSON(Person_ID)
);

CREATE TABLE dbo.LEASE_AGREEMENT (
    Lease_ID INT IDENTITY(1,1) PRIMARY KEY,
    Property_ID INT NOT NULL,
    Tenant_ID INT NOT NULL,
    Start_Date DATE NOT NULL,
    End_Date DATE NOT NULL,
    Move_In_Date DATE,
    Document_URL VARCHAR(255),
    CONSTRAINT FK_Lease_Property FOREIGN KEY (Property_ID) REFERENCES dbo.PROPERTY(Property_ID),
    CONSTRAINT FK_Lease_Tenant FOREIGN KEY (Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID),
    CONSTRAINT CHK_Lease_Dates CHECK (End_Date > Start_Date)
);

CREATE TABLE dbo.SUB_LEASE (
    SubLease_ID INT IDENTITY(1,1) PRIMARY KEY,
    Tenant_ID INT NOT NULL,
    Start_Date DATE NOT NULL,
    End_Date DATE NOT NULL,
    Pro_Rated_Cost DECIMAL(10,2),
    CONSTRAINT FK_SubLease_Tenant FOREIGN KEY (Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID),
    CONSTRAINT CHK_SubLease_Dates CHECK (End_Date > Start_Date)
);

CREATE TABLE dbo.GUEST (
    Guest_ID INT IDENTITY(1,1) PRIMARY KEY,
    Tenant_ID INT NOT NULL,
    First_Name VARCHAR(50) NOT NULL,
    Last_Name VARCHAR(50) NOT NULL,
    Arrival_Date DATE,
    Is_Overnight BIT DEFAULT 0,
    CONSTRAINT FK_Guest_Tenant FOREIGN KEY (Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID)
);

-- [C. Inventory System]
CREATE TABLE dbo.INVENTORY_ITEM (
    Item_ID INT IDENTITY(1,1) PRIMARY KEY,
    Item_Name VARCHAR(100) NOT NULL,
    Total_Quantity INT DEFAULT 0,
    Category VARCHAR(50),
    Storage_Location VARCHAR(100),
    CONSTRAINT CHK_Inventory_Qty CHECK (Total_Quantity >= 0)
);

CREATE TABLE dbo.SHARED_ITEM (
    Item_ID INT PRIMARY KEY,
    Property_ID INT NOT NULL,
    Low_Stock_Threshold INT DEFAULT 1,
    Auto_Replenish_Flag BIT DEFAULT 0,
    CONSTRAINT FK_SharedItem_Inv FOREIGN KEY (Item_ID) REFERENCES dbo.INVENTORY_ITEM(Item_ID),
    CONSTRAINT FK_SharedItem_Property FOREIGN KEY (Property_ID) REFERENCES dbo.PROPERTY(Property_ID)
);

CREATE TABLE dbo.PERSONAL_ITEM (
    Item_ID INT PRIMARY KEY,
    Tenant_ID INT NOT NULL,
    Is_Private BIT DEFAULT 1,
    CONSTRAINT FK_PersonalItem_Inv FOREIGN KEY (Item_ID) REFERENCES dbo.INVENTORY_ITEM(Item_ID),
    CONSTRAINT FK_PersonalItem_Tenant FOREIGN KEY (Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID)
);

-- [D. Financial Management]
CREATE TABLE dbo.EXPENSE (
    Expense_ID INT IDENTITY(1,1) PRIMARY KEY,
    Paid_By_Tenant_ID INT NOT NULL,
    Total_Amount DECIMAL(10,2) NOT NULL,
    Date_Incurred DATE NOT NULL,
    Split_Policy VARCHAR(50),
    Receipt_Image VARCHAR(255),
    CONSTRAINT FK_Expense_Tenant FOREIGN KEY (Paid_By_Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID),
    CONSTRAINT CHK_Expense_Amount CHECK (Total_Amount > 0)
);

CREATE TABLE dbo.EXPENSE_SHARE (
    Share_ID INT IDENTITY(1,1) PRIMARY KEY,
    Expense_ID INT NOT NULL,
    Owed_By_Tenant_ID INT NOT NULL,
    Owed_Amount DECIMAL(10,2) NOT NULL,
    Status VARCHAR(20) DEFAULT 'Pending',
    CONSTRAINT FK_ExpenseShare_Exp FOREIGN KEY (Expense_ID) REFERENCES dbo.EXPENSE(Expense_ID),
    CONSTRAINT FK_ExpenseShare_Tenant FOREIGN KEY (Owed_By_Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID),
    CONSTRAINT CHK_ExpShare_Status CHECK (Status IN ('Pending', 'Paid')) -- NEW
);

CREATE TABLE dbo.PAYMENT (
    Payment_ID INT IDENTITY(1,1) PRIMARY KEY,
    Payer_Tenant_ID INT NOT NULL,
    Amount DECIMAL(10,2) NOT NULL,
    Payment_Date DATE NOT NULL,
    Note VARCHAR(255),
    CONSTRAINT FK_Payment_Tenant FOREIGN KEY (Payer_Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID)
);

-- [E. Chores & Governance]
CREATE TABLE dbo.CHORE_DEFINITION (
    Chore_ID INT IDENTITY(1,1) PRIMARY KEY,
    Task_Name VARCHAR(100) NOT NULL,
    Description VARCHAR(255),
    Difficulty_Weight INT,
    Frequency VARCHAR(50)
);

CREATE TABLE dbo.CHORE_ASSIGNMENT (
    Assignment_ID INT IDENTITY(1,1) PRIMARY KEY,
    Chore_ID INT NOT NULL,
    Assigned_Tenant_ID INT NOT NULL,
    Due_Date DATE,
    Completion_Date DATE,
    Status VARCHAR(20) DEFAULT 'Pending',
    Proof_Image VARCHAR(255),
    CONSTRAINT FK_ChoreAssign_Chore FOREIGN KEY (Chore_ID) REFERENCES dbo.CHORE_DEFINITION(Chore_ID),
    CONSTRAINT FK_ChoreAssign_Tenant FOREIGN KEY (Assigned_Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID),
    CONSTRAINT CHK_Chore_Status CHECK (Status IN ('Pending', 'Completed')) -- NEW
);

CREATE TABLE dbo.PROPOSAL (
    Proposal_ID INT IDENTITY(1,1) PRIMARY KEY,
    Proposed_By_Tenant_ID INT NOT NULL,
    Description VARCHAR(255) NOT NULL,
    Cost_Threshold DECIMAL(10,2),
    Status VARCHAR(20) DEFAULT 'Active',
    CONSTRAINT FK_Proposal_Tenant FOREIGN KEY (Proposed_By_Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID),
    CONSTRAINT CHK_Prop_Status CHECK (Status IN ('Active', 'Approved', 'Rejected')) -- NEW
);

CREATE TABLE dbo.VOTE (
    Vote_ID INT IDENTITY(1,1) PRIMARY KEY,
    Proposal_ID INT NOT NULL,
    Tenant_ID INT NOT NULL,
    Approval_Status BIT NOT NULL,
    Vote_Timestamp DATETIME NOT NULL,
    CONSTRAINT FK_Vote_Proposal FOREIGN KEY (Proposal_ID) REFERENCES dbo.PROPOSAL(Proposal_ID),
    CONSTRAINT FK_Vote_Tenant FOREIGN KEY (Tenant_ID) REFERENCES dbo.TENANT(Tenant_ID),
    CONSTRAINT UQ_Vote_Tenant_Proposal UNIQUE (Proposal_ID, Tenant_ID) -- NEW (Prevents duplicate votes)
);

-- [F. Utility Analytics]
CREATE TABLE dbo.UTILITY_TYPE (
    Utility_Type_ID INT IDENTITY(1,1) PRIMARY KEY,
    Type_Name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE dbo.UTILITY_READING (
    Reading_ID INT IDENTITY(1,1) PRIMARY KEY,
    Property_ID INT NOT NULL,
    Utility_Type_ID INT NOT NULL,
    Provider_Name VARCHAR(100),
    Meter_Value DECIMAL(10,2) NOT NULL,
    Reading_Date DATE NOT NULL,
    CONSTRAINT FK_Utility_Property FOREIGN KEY (Property_ID) REFERENCES dbo.PROPERTY(Property_ID),
    CONSTRAINT FK_Utility_Type FOREIGN KEY (Utility_Type_ID) REFERENCES dbo.UTILITY_TYPE(Utility_Type_ID)
);
GO