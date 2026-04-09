-- Test fixture for lint_access.py
-- This file contains intentional Access SQL violations to verify linter rules.
-- Every rule (AV001-AV008) should fire at least once.

-- AV001: Reserved word used as table name without bracket escaping
CREATE TABLE Select (
    ID AUTOINCREMENT PRIMARY KEY,
    Name TEXT(100) NOT NULL
);

-- AV001: Reserved word used as field name without brackets
CREATE TABLE TestTable (
    ID AUTOINCREMENT PRIMARY KEY,
    From TEXT(100),
    Where TEXT(200)
);

-- AV002: Deprecated data type (SINGLE)
CREATE TABLE BadTypes (
    ID AUTOINCREMENT PRIMARY KEY,
    Amount SINGLE,
    RawData BINARY(100)
);

-- AV003: Name with spaces (needs bracket escaping)
CREATE TABLE My Table (
    ID AUTOINCREMENT PRIMARY KEY,
    First Name TEXT(100)
);

-- AV004: Missing semicolon terminator
CREATE TABLE NoSemicolon (
    ID AUTOINCREMENT PRIMARY KEY,
    Name TEXT(100) NOT NULL
)

-- AV005: SELECT * usage
SELECT * FROM Departments;
SELECT * FROM Clients WHERE Active = -1;

-- AV007: Table name not in PascalCase
CREATE TABLE bad_table_name (
    ID AUTOINCREMENT PRIMARY KEY,
    value TEXT(50)
);

-- AV008: AUTOINCREMENT on non-LONG field
CREATE TABLE BadAutoIncrement (
    ID INTEGER AUTOINCREMENT PRIMARY KEY,
    Name TEXT(100)
);

-- Clean example (should not trigger any warnings)
CREATE TABLE [Good_Table] (
    ID LONG AUTOINCREMENT PRIMARY KEY,
    [Department_Name] TEXT(100) NOT NULL,
    Active BIT
);

INSERT INTO Departments (Department_Name, Active) VALUES ('Finance', -1);
