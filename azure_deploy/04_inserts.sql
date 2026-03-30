-- USE CoHabitant;
-- GO

-- ============================================================================
-- CoHabitant — Demo Seed Data (v2)
-- ============================================================================
-- Key fix: Multiple tenants per property so roommate features actually work.
--
-- Property layout:
--   Property 1 (123 Maple St, Boston):    Kevin(11), Laura(12), Michael(13)  ← main demo house
--   Property 2 (456 Oak Ave, Boston):      Nina(14), Oscar(15), Pam(16)
--   Property 3 (789 Pine Blvd, Cambridge): Quinn(17), Ryan(18)
--   Property 4 (101 Elm St, Somerville):   Stanley(19)                       ← solo tenant
--   Property 5 (202 Cedar Rd, Brookline):  Toby(20)                          ← solo tenant
--   Properties 6-10: Empty (available for onboarding demo)
--
-- All expenses, shares, payments, votes, and chores are scoped within
-- the same property — matching exactly what the SPs enforce at runtime.
-- ============================================================================

-- 1. PERSON (20 rows: 10 Landlords + 10 Tenants)
SET IDENTITY_INSERT dbo.PERSON ON;
INSERT INTO dbo.PERSON (Person_ID, First_Name, Last_Name, Email, Phone_Number) VALUES
(1, 'Alice', 'Smith', 'alice.landlord@email.com', '555-0101'),
(2, 'Bob', 'Jones', 'bob.properties@email.com', '555-0102'),
(3, 'Charlie', 'Brown', 'cbrown.investments@email.com', '555-0103'),
(4, 'Diana', 'Prince', 'dprince.realestate@email.com', '555-0104'),
(5, 'Evan', 'Wright', 'ewright.mgmt@email.com', '555-0105'),
(6, 'Fiona', 'Gallagher', 'fiona.g@email.com', '555-0106'),
(7, 'George', 'Costanza', 'vandelay.ind@email.com', '555-0107'),
(8, 'Hannah', 'Abbott', 'habbott.rentals@email.com', '555-0108'),
(9, 'Ian', 'Malcolm', 'chaos.theory.props@email.com', '555-0109'),
(10, 'Julia', 'Child', 'jchild.estates@email.com', '555-0110'),
(11, 'Kevin', 'Malone', 'kmalone.tenant@email.com', '555-0201'),
(12, 'Laura', 'Palmer', 'lpalmer.tenant@email.com', '555-0202'),
(13, 'Michael', 'Scott', 'mscott.tenant@email.com', '555-0203'),
(14, 'Nina', 'Tucker', 'ntucker.tenant@email.com', '555-0204'),
(15, 'Oscar', 'Martinez', 'omartinez.tenant@email.com', '555-0205'),
(16, 'Pam', 'Beesly', 'pbeesly.tenant@email.com', '555-0206'),
(17, 'Quinn', 'Fabray', 'qfabray.tenant@email.com', '555-0207'),
(18, 'Ryan', 'Howard', 'rhoward.tenant@email.com', '555-0208'),
(19, 'Stanley', 'Hudson', 'shudson.tenant@email.com', '555-0209'),
(20, 'Toby', 'Flenderson', 'tflenderson.tenant@email.com', '555-0210');
SET IDENTITY_INSERT dbo.PERSON OFF;
GO

-- 2. LANDLORD (10 landlords, properties 6-10 are empty — ready for demo)
INSERT INTO dbo.LANDLORD (Landlord_ID, Bank_Details, Tax_ID) VALUES
(1, 'Chase Bank - Acct 1234', 'TAX-111'),
(2, 'Bank of America - Acct 5678', 'TAX-222'),
(3, 'Wells Fargo - Acct 9012', 'TAX-333'),
(4, 'CitiBank - Acct 3456', 'TAX-444'),
(5, 'Capital One - Acct 7890', 'TAX-555'),
(6, 'Discover - Acct 2345', 'TAX-666'),
(7, 'US Bank - Acct 6789', 'TAX-777'),
(8, 'PNC Bank - Acct 0123', 'TAX-888'),
(9, 'TD Bank - Acct 4567', 'TAX-999'),
(10, 'Truist - Acct 8901', 'TAX-000');
GO

-- 3. PROPERTY (10 properties; tenants on 1-5 only)
SET IDENTITY_INSERT dbo.PROPERTY ON;
INSERT INTO dbo.PROPERTY (Property_ID, Landlord_ID, Street_Address, City, State, Zip_Code, Max_Occupancy, WiFi_Password) VALUES
(1, 1, '123 Maple St', 'Boston', 'MA', '02115', 4, 'mapleTree123'),
(2, 2, '456 Oak Ave', 'Boston', 'MA', '02116', 3, 'oakWood456'),
(3, 3, '789 Pine Blvd', 'Cambridge', 'MA', '02139', 5, 'pineCone789'),
(4, 4, '101 Elm St', 'Somerville', 'MA', '02144', 2, 'elmLeaf101'),
(5, 5, '202 Cedar Rd', 'Brookline', 'MA', '02446', 4, 'cedarBranch202'),
(6, 6, '303 Birch Ln', 'Boston', 'MA', '02115', 6, 'birchBark303'),
(7, 7, '404 Ash Dr', 'Cambridge', 'MA', '02138', 3, 'ashTray404'),
(8, 8, '505 Spruce Ct', 'Somerville', 'MA', '02143', 4, 'spruceGoose505'),
(9, 9, '606 Walnut Pl', 'Boston', 'MA', '02120', 5, 'walnutShell606'),
(10, 10, '707 Chestnut Ter', 'Brookline', 'MA', '02445', 2, 'chestNut707');
SET IDENTITY_INSERT dbo.PROPERTY OFF;
GO

-- 4. TENANT (balances reflect the seed expense/payment data below)
INSERT INTO dbo.TENANT (Tenant_ID, Current_Net_Balance, Emergency_Contact, Tenant_Responsibility_Score) VALUES
(11, 50.00, 'Mom: 555-9001', 95),       -- Kevin  (Property 1) net positive
(12, -35.00, 'Dad: 555-9002', 88),      -- Laura  (Property 1) net negative
(13, -15.00, 'Sister: 555-9003', 100),  -- Michael(Property 1)
(14, 40.00, 'Brother: 555-9004', 82),   -- Nina   (Property 2) net positive
(15, -10.00, 'Friend: 555-9005', 92),   -- Oscar  (Property 2)
(16, -30.00, 'Aunt: 555-9006', 85),     -- Pam    (Property 2) net negative
(17, 15.00, 'Uncle: 555-9007', 98),      -- Quinn  (Property 3)
(18, -15.00, 'Mom: 555-9008', 100),     -- Ryan   (Property 3)
(19, 0.00, 'Dad: 555-9009', 75),         -- Stanley(Property 4) solo
(20, 0.00, 'Sister: 555-9010', 89);      -- Toby   (Property 5) solo
GO

-- 5. LEASE_AGREEMENT — THE KEY FIX: multiple tenants per property
SET IDENTITY_INSERT dbo.LEASE_AGREEMENT ON;
INSERT INTO dbo.LEASE_AGREEMENT (Lease_ID, Property_ID, Tenant_ID, Start_Date, End_Date, Move_In_Date, Document_URL) VALUES
-- Property 1: Kevin, Laura, Michael (3 roommates)
(1, 1, 11, '2025-09-01', '2026-08-31', '2025-09-01', 'https://cohabitant.com/lease1.pdf'),
(2, 1, 12, '2025-09-01', '2026-08-31', '2025-09-05', 'https://cohabitant.com/lease2.pdf'),
(3, 1, 13, '2025-09-01', '2026-08-31', '2025-09-03', 'https://cohabitant.com/lease3.pdf'),
-- Property 2: Nina, Oscar, Pam (3 roommates)
(4, 2, 14, '2025-09-01', '2026-08-31', '2025-09-01', 'https://cohabitant.com/lease4.pdf'),
(5, 2, 15, '2025-09-01', '2026-08-31', '2025-09-02', 'https://cohabitant.com/lease5.pdf'),
(6, 2, 16, '2025-09-01', '2026-08-31', '2025-09-01', 'https://cohabitant.com/lease6.pdf'),
-- Property 3: Quinn, Ryan (2 roommates)
(7, 3, 17, '2025-09-01', '2026-08-31', '2025-09-01', 'https://cohabitant.com/lease7.pdf'),
(8, 3, 18, '2025-09-01', '2026-08-31', '2025-09-02', 'https://cohabitant.com/lease8.pdf'),
-- Property 4: Stanley (solo)
(9, 4, 19, '2025-09-01', '2026-08-31', '2025-09-01', 'https://cohabitant.com/lease9.pdf'),
-- Property 5: Toby (solo)
(10, 5, 20, '2025-09-01', '2026-08-31', '2025-09-01', 'https://cohabitant.com/lease10.pdf');
SET IDENTITY_INSERT dbo.LEASE_AGREEMENT OFF;
GO

-- 6. SUB_LEASE (within lease windows)
SET IDENTITY_INSERT dbo.SUB_LEASE ON;
INSERT INTO dbo.SUB_LEASE (SubLease_ID, Tenant_ID, Start_Date, End_Date, Pro_Rated_Cost) VALUES
(1, 11, '2026-06-01', '2026-08-31', 1200.00),
(2, 12, '2026-06-01', '2026-08-31', 1200.00),
(3, 14, '2026-06-01', '2026-08-31', 1100.00),
(4, 17, '2026-06-01', '2026-08-31', 1400.00);
SET IDENTITY_INSERT dbo.SUB_LEASE OFF;
GO

-- 7. GUEST (registered by tenants)
SET IDENTITY_INSERT dbo.GUEST ON;
INSERT INTO dbo.GUEST (Guest_ID, Tenant_ID, First_Name, Last_Name, Arrival_Date, Is_Overnight) VALUES
(1, 11, 'John', 'Doe', '2026-03-15', 1),
(2, 11, 'Jane', 'Doe', '2026-03-15', 1),
(3, 12, 'Mike', 'Johnson', '2026-03-17', 0),
(4, 13, 'Emily', 'Davis', '2026-03-18', 1),
(5, 14, 'Chris', 'Wilson', '2026-03-19', 0),
(6, 15, 'Sarah', 'Brown', '2026-03-20', 1),
(7, 17, 'David', 'Taylor', '2026-03-21', 1),
(8, 18, 'Jessica', 'Anderson', '2026-03-22', 0),
(9, 19, 'Matthew', 'Thomas', '2026-03-23', 1),
(10, 20, 'Ashley', 'Jackson', '2026-03-24', 0);
SET IDENTITY_INSERT dbo.GUEST OFF;
GO

-- 8. INVENTORY_ITEM (20 items)
SET IDENTITY_INSERT dbo.INVENTORY_ITEM ON;
INSERT INTO dbo.INVENTORY_ITEM (Item_ID, Item_Name, Total_Quantity, Category, Storage_Location) VALUES
-- Shared items (will link to properties)
(1, 'Paper Towels', 6, 'Cleaning', 'Kitchen Pantry'),
(2, 'Dish Soap', 2, 'Cleaning', 'Under Sink'),
(3, 'Toilet Paper', 12, 'Bathroom', 'Hall Closet'),
(4, 'Trash Bags', 30, 'Kitchen', 'Under Sink'),
(5, 'Olive Oil', 1, 'Groceries', 'Kitchen Cabinet'),
(6, 'All-Purpose Cleaner', 2, 'Cleaning', 'Utility Closet'),
(7, 'Laundry Detergent', 1, 'Cleaning', 'Laundry Room'),
(8, 'Sponges', 4, 'Cleaning', 'Under Sink'),
(9, 'Coffee Filters', 50, 'Kitchen', 'Pantry'),
(10, 'Salt', 1, 'Groceries', 'Kitchen Spice Rack'),
-- Personal items (will link to tenants)
(11, 'Protein Powder', 1, 'Groceries', 'Tenant Shelf'),
(12, 'Almond Milk', 2, 'Groceries', 'Fridge Top Shelf'),
(13, 'Hair Gel', 1, 'Personal Care', 'Bathroom Vanity'),
(14, 'Expensive Shampoo', 1, 'Personal Care', 'Shower Caddy'),
(15, 'Gaming Controller', 2, 'Electronics', 'Living Room'),
(16, 'Laptop Charger', 1, 'Electronics', 'Bedroom'),
(17, 'Specialty Coffee', 1, 'Groceries', 'Pantry'),
(18, 'Greek Yogurt', 4, 'Groceries', 'Fridge Bottom Shelf'),
(19, 'Toothpaste', 1, 'Personal Care', 'Bathroom Cabinet'),
(20, 'Electric Razor', 1, 'Personal Care', 'Bathroom Drawer');
SET IDENTITY_INSERT dbo.INVENTORY_ITEM OFF;
GO

-- 9. SHARED_ITEM (linked to properties with tenants)
INSERT INTO dbo.SHARED_ITEM (Item_ID, Property_ID, Low_Stock_Threshold, Auto_Replenish_Flag) VALUES
(1, 1, 2, 1),   -- Paper Towels → Property 1 (Kevin/Laura/Michael)
(2, 1, 1, 0),   -- Dish Soap → Property 1
(3, 1, 4, 1),   -- Toilet Paper → Property 1
(4, 2, 10, 0),  -- Trash Bags → Property 2 (Nina/Oscar/Pam)
(5, 2, 1, 0),   -- Olive Oil → Property 2
(6, 2, 1, 1),   -- Cleaner → Property 2
(7, 3, 1, 1),   -- Laundry Detergent → Property 3 (Quinn/Ryan)
(8, 3, 2, 0),   -- Sponges → Property 3
(9, 1, 10, 0),  -- Coffee Filters → Property 1
(10, 3, 1, 0);  -- Salt → Property 3
GO

-- 10. PERSONAL_ITEM (linked to individual tenants)
INSERT INTO dbo.PERSONAL_ITEM (Item_ID, Tenant_ID, Is_Private) VALUES
(11, 11, 1),  -- Kevin's Protein Powder
(12, 12, 0),  -- Laura's Almond Milk (not private — roommates can use)
(13, 13, 1),  -- Michael's Hair Gel
(14, 14, 1),  -- Nina's Shampoo
(15, 15, 0),  -- Oscar's Gaming Controller (shared with house)
(16, 16, 1),  -- Pam's Laptop Charger
(17, 17, 1),  -- Quinn's Specialty Coffee
(18, 18, 1),  -- Ryan's Greek Yogurt
(19, 19, 1),  -- Stanley's Toothpaste
(20, 20, 1);  -- Toby's Electric Razor
GO

-- 11. EXPENSE (property-scoped: payer and debtors share the same property)
--
-- Property 1 (Kevin, Laura, Michael):
--   Exp 1: Kevin paid $120 groceries (Equal, 3-way)
--   Exp 2: Laura paid $90 internet (Equal, 3-way)
--   Exp 3: Michael paid $60 cleaning supplies (Equal, 3-way)
--   Exp 4: Kevin paid $45 takeout (Custom — Laura only, Michael didn't eat)
--
-- Property 2 (Nina, Oscar, Pam):
--   Exp 5: Nina paid $150 deep cleaning (Equal, 3-way)
--   Exp 6: Oscar paid $75 utility split (Equal, 3-way)
--   Exp 7: Pam paid $42 household supplies (Equal, 3-way)
--
-- Property 3 (Quinn, Ryan):
--   Exp 8: Quinn paid $80 groceries (Equal, 2-way)
--   Exp 9: Ryan paid $50 cleaning (Equal, 2-way)
--
-- Solo (no shares created):
--   Exp 10: Stanley paid $30 personal supplies
--
SET IDENTITY_INSERT dbo.EXPENSE ON;
INSERT INTO dbo.EXPENSE (Expense_ID, Paid_By_Tenant_ID, Total_Amount, Date_Incurred, Split_Policy, Receipt_Image) VALUES
(1, 11, 120.00, '2026-03-01', 'Equal', 'receipt_groceries_mar.jpg'),
(2, 12, 90.00, '2026-03-05', 'Equal', 'receipt_internet_mar.jpg'),
(3, 13, 60.00, '2026-03-10', 'Equal', 'receipt_cleaning.jpg'),
(4, 11, 45.00, '2026-03-14', 'Custom', 'receipt_takeout.jpg'),
(5, 14, 150.00, '2026-03-03', 'Equal', 'receipt_deepclean.jpg'),
(6, 15, 75.00, '2026-03-08', 'Equal', 'receipt_utilities.jpg'),
(7, 16, 42.00, '2026-03-12', 'Equal', 'receipt_supplies.jpg'),
(8, 17, 80.00, '2026-03-06', 'Equal', 'receipt_groceries_q.jpg'),
(9, 18, 50.00, '2026-03-15', 'Equal', 'receipt_cleaning_r.jpg'),
(10, 19, 30.00, '2026-03-20', 'Equal', NULL);
SET IDENTITY_INSERT dbo.EXPENSE OFF;
GO

-- 12. EXPENSE_SHARE (all within same property as the expense payer)
SET IDENTITY_INSERT dbo.EXPENSE_SHARE ON;
INSERT INTO dbo.EXPENSE_SHARE (Share_ID, Expense_ID, Owed_By_Tenant_ID, Owed_Amount, Status) VALUES
-- Property 1: Expense 1 (Kevin paid $120 → Laura $40, Michael $40)
(1, 1, 12, 40.00, 'Pending'),
(2, 1, 13, 40.00, 'Pending'),
-- Property 1: Expense 2 (Laura paid $90 → Kevin $30, Michael $30)
(3, 2, 11, 30.00, 'Paid'),      -- Kevin settled this
(4, 2, 13, 30.00, 'Pending'),
-- Property 1: Expense 3 (Michael paid $60 → Kevin $20, Laura $20)
(5, 3, 11, 20.00, 'Pending'),
(6, 3, 12, 20.00, 'Pending'),
-- Property 1: Expense 4 (Kevin paid $45 custom → Laura $45 only)
(7, 4, 12, 45.00, 'Pending'),
-- Property 2: Expense 5 (Nina paid $150 → Oscar $50, Pam $50)
(8, 5, 15, 50.00, 'Paid'),      -- Oscar settled this
(9, 5, 16, 50.00, 'Pending'),
-- Property 2: Expense 6 (Oscar paid $75 → Nina $25, Pam $25)
(10, 6, 14, 25.00, 'Pending'),
(11, 6, 16, 25.00, 'Pending'),
-- Property 2: Expense 7 (Pam paid $42 → Nina $14, Oscar $14)
(12, 7, 14, 14.00, 'Pending'),
(13, 7, 15, 14.00, 'Pending'),
-- Property 3: Expense 8 (Quinn paid $80 → Ryan $40)
(14, 8, 18, 40.00, 'Pending'),
-- Property 3: Expense 9 (Ryan paid $50 → Quinn $25)
(15, 9, 17, 25.00, 'Paid');      -- Quinn settled this
SET IDENTITY_INSERT dbo.EXPENSE_SHARE OFF;
GO

-- 13. PAYMENT (settlements only between roommates on the SAME property)
SET IDENTITY_INSERT dbo.PAYMENT ON;
INSERT INTO dbo.PAYMENT (Payment_ID, Payer_Tenant_ID, Payee_Tenant_ID, Amount, Payment_Date, Note, Payment_Type) VALUES
-- Property 1: Kevin settles his $30 debt to Laura (from Expense 2)
(1, 11, 12, 30.00, '2026-03-07', 'Internet bill — my share', 'Settlement'),
-- Property 2: Oscar settles his $50 debt to Nina (from Expense 5)
(2, 15, 14, 50.00, '2026-03-09', 'Deep cleaning — my share', 'Settlement'),
-- Property 3: Quinn settles her $25 debt to Ryan (from Expense 9)
(3, 17, 18, 25.00, '2026-03-18', 'Cleaning supplies — settled', 'Settlement');
SET IDENTITY_INSERT dbo.PAYMENT OFF;
GO

-- 14. CHORE_DEFINITION (10 reusable chore templates)
SET IDENTITY_INSERT dbo.CHORE_DEFINITION ON;
INSERT INTO dbo.CHORE_DEFINITION (Chore_ID, Task_Name, Description, Difficulty_Weight, Frequency) VALUES
(1, 'Take Out Trash', 'Empty kitchen and bathroom bins to curbside.', 2, 'Weekly'),
(2, 'Clean Kitchen', 'Wipe counters, clean sink, sweep floor.', 5, 'Weekly'),
(3, 'Vacuum Living Room', 'Vacuum rug and floors in common area.', 3, 'Bi-Weekly'),
(4, 'Clean Bathroom', 'Scrub toilet, shower, and sink.', 7, 'Weekly'),
(5, 'Mop Floors', 'Mop kitchen and hardwood areas.', 4, 'Bi-Weekly'),
(6, 'Dust Furniture', 'Dust shelves and TV stand.', 2, 'Monthly'),
(7, 'Clean Fridge', 'Throw out expired food and wipe shelves.', 6, 'Monthly'),
(8, 'Organize Pantry', 'Rearrange items neatly.', 3, 'Monthly'),
(9, 'Take Out Recycling', 'Sort and take recycling bins out.', 2, 'Weekly'),
(10, 'Deep Clean Oven', 'Use oven cleaner and scrub interior.', 8, 'Quarterly');
SET IDENTITY_INSERT dbo.CHORE_DEFINITION OFF;
GO

-- 15. CHORE_ASSIGNMENT (assigned to tenants — mix of completed and pending)
SET IDENTITY_INSERT dbo.CHORE_ASSIGNMENT ON;
INSERT INTO dbo.CHORE_ASSIGNMENT (Assignment_ID, Chore_ID, Assigned_Tenant_ID, Due_Date, Completion_Date, Status, Proof_Image) VALUES
-- Property 1 chores (Kevin, Laura, Michael)
(1, 1, 11, '2026-03-05', '2026-03-05', 'Completed', 'trash_done.jpg'),
(2, 2, 12, '2026-03-07', NULL, 'Pending', NULL),
(3, 3, 13, '2026-03-10', '2026-03-09', 'Completed', 'vacuum_done.jpg'),
(4, 4, 11, '2026-03-14', NULL, 'Pending', NULL),
(5, 7, 12, '2026-03-20', NULL, 'Pending', NULL),
(6, 9, 13, '2026-03-12', '2026-03-12', 'Completed', 'recycling_done.jpg'),
-- Property 2 chores (Nina, Oscar, Pam)
(7, 5, 14, '2026-03-15', '2026-03-15', 'Completed', 'mop_done.jpg'),
(8, 6, 15, '2026-03-20', NULL, 'Pending', NULL),
(9, 8, 16, '2026-03-25', NULL, 'Pending', NULL),
-- Property 3 chores (Quinn, Ryan)
(10, 10, 17, '2026-04-01', NULL, 'Pending', NULL),
(11, 1, 18, '2026-03-19', '2026-03-19', 'Completed', 'trash_done_r.jpg'),
-- Solo
(12, 2, 19, '2026-03-28', NULL, 'Pending', NULL);
SET IDENTITY_INSERT dbo.CHORE_ASSIGNMENT OFF;
GO

-- 16. PROPOSAL (proposed by tenants — roommates on same property vote)
SET IDENTITY_INSERT dbo.PROPOSAL ON;
INSERT INTO dbo.PROPOSAL (Proposal_ID, Proposed_By_Tenant_ID, Description, Cost_Threshold, Status) VALUES
-- Property 1 proposals
(1, 11, 'Buy a new living room rug', 150.00, 'Active'),
(2, 12, 'Implement quiet hours after 11 PM', 0.00, 'Approved'),
(3, 13, 'Upgrade internet to 1 Gbps', 20.00, 'Active'),
-- Property 2 proposals
(4, 14, 'Hire bi-weekly cleaning service', 100.00, 'Rejected'),
(5, 15, 'Split cost for a shared air fryer', 80.00, 'Approved'),
(6, 16, 'Change thermostat default to 70°F', 0.00, 'Active'),
-- Property 3 proposals
(7, 17, 'Get a house Netflix account', 15.00, 'Approved'),
(8, 18, 'No overnight guests during finals', 0.00, 'Active');
SET IDENTITY_INSERT dbo.PROPOSAL OFF;
GO

-- 17. VOTE (voters must be roommates of the proposer — same property)
SET IDENTITY_INSERT dbo.VOTE ON;
INSERT INTO dbo.VOTE (Vote_ID, Proposal_ID, Tenant_ID, Approval_Status, Vote_Timestamp) VALUES
-- Prop 1 (Kevin's, Property 1): Laura votes Yes
(1, 1, 12, 1, '2026-03-01 10:00:00'),
-- Prop 2 (Laura's, Property 1): Kevin votes Yes, Michael votes Yes → Approved
(2, 2, 11, 1, '2026-03-02 11:30:00'),
(3, 2, 13, 1, '2026-03-02 14:15:00'),
-- Prop 3 (Michael's, Property 1): Kevin votes No (still Active, Laura hasn't voted)
(4, 3, 11, 0, '2026-03-03 09:00:00'),
-- Prop 4 (Nina's, Property 2): Oscar No, Pam No → Rejected
(5, 4, 15, 0, '2026-03-04 09:45:00'),
(6, 4, 16, 0, '2026-03-04 10:30:00'),
-- Prop 5 (Oscar's, Property 2): Nina Yes, Pam Yes → Approved
(7, 5, 14, 1, '2026-03-05 16:20:00'),
(8, 5, 16, 1, '2026-03-05 17:00:00'),
-- Prop 7 (Quinn's, Property 3): Ryan votes Yes → Approved
(9, 7, 18, 1, '2026-03-07 20:10:00');
SET IDENTITY_INSERT dbo.VOTE OFF;
GO

-- 18. UTILITY_TYPE (lookup table)
SET IDENTITY_INSERT dbo.UTILITY_TYPE ON;
INSERT INTO dbo.UTILITY_TYPE (Utility_Type_ID, Type_Name) VALUES
(1, 'Electricity'),
(2, 'Water'),
(3, 'Gas'),
(4, 'Internet'),
(5, 'Trash Collection');
SET IDENTITY_INSERT dbo.UTILITY_TYPE OFF;
GO

-- 19. UTILITY_READING (multi-month data for analytics trends)
--     Focused on Properties 1-3 so tenants can see their analytics
SET IDENTITY_INSERT dbo.UTILITY_READING ON;
INSERT INTO dbo.UTILITY_READING (Reading_ID, Property_ID, Utility_Type_ID, Provider_Name, Meter_Value, Reading_Date) VALUES
-- Property 1 — January
(1, 1, 1, 'Eversource', 145.50, '2026-01-15'),
(2, 1, 2, 'MWRA', 62.30, '2026-01-15'),
(3, 1, 3, 'National Grid', 98.75, '2026-01-15'),
-- Property 1 — February
(4, 1, 1, 'Eversource', 138.20, '2026-02-15'),
(5, 1, 2, 'MWRA', 58.10, '2026-02-15'),
(6, 1, 3, 'National Grid', 105.40, '2026-02-15'),
-- Property 1 — March
(7, 1, 1, 'Eversource', 125.80, '2026-03-15'),
(8, 1, 2, 'MWRA', 55.20, '2026-03-15'),
(9, 1, 3, 'National Grid', 89.60, '2026-03-15'),
(10, 1, 4, 'Comcast', 79.99, '2026-03-15'),
-- Property 2 — February
(11, 2, 1, 'Eversource', 132.40, '2026-02-15'),
(12, 2, 2, 'MWRA', 48.70, '2026-02-15'),
-- Property 2 — March
(13, 2, 1, 'Eversource', 128.90, '2026-03-15'),
(14, 2, 2, 'MWRA', 51.30, '2026-03-15'),
(15, 2, 3, 'National Grid', 76.50, '2026-03-15'),
-- Property 3 — March
(16, 3, 1, 'Eversource', 112.60, '2026-03-15'),
(17, 3, 4, 'Comcast', 69.99, '2026-03-15');
SET IDENTITY_INSERT dbo.UTILITY_READING OFF;
GO
