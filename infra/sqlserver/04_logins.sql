SET NOCOUNT ON;

IF SUSER_ID(N'$(EtlUser)') IS NULL
    CREATE LOGIN [$(EtlUser)] WITH PASSWORD = N'$(EtlPassword)', CHECK_POLICY = OFF;
ELSE
    ALTER LOGIN [$(EtlUser)] WITH PASSWORD = N'$(EtlPassword)';

IF SUSER_ID(N'$(AppUser)') IS NULL
    CREATE LOGIN [$(AppUser)] WITH PASSWORD = N'$(AppPassword)', CHECK_POLICY = OFF;
ELSE
    ALTER LOGIN [$(AppUser)] WITH PASSWORD = N'$(AppPassword)';

GRANT VIEW SERVER STATE TO [$(EtlUser)];
GO

USE Students;
IF USER_ID(N'$(EtlUser)') IS NULL CREATE USER [$(EtlUser)] FOR LOGIN [$(EtlUser)];
ALTER ROLE db_datareader ADD MEMBER [$(EtlUser)];
GRANT SELECT ON SCHEMA::cdc TO [$(EtlUser)];
GRANT VIEW DATABASE STATE TO [$(EtlUser)];

IF USER_ID(N'$(AppUser)') IS NULL CREATE USER [$(AppUser)] FOR LOGIN [$(AppUser)];
ALTER ROLE db_datareader ADD MEMBER [$(AppUser)];
ALTER ROLE db_datawriter ADD MEMBER [$(AppUser)];
DENY SELECT ON SCHEMA::cdc TO [$(AppUser)];
GO

USE StudentsPortal;
IF USER_ID(N'$(AppUser)') IS NULL CREATE USER [$(AppUser)] FOR LOGIN [$(AppUser)];
ALTER ROLE db_datareader ADD MEMBER [$(AppUser)];
ALTER ROLE db_datawriter ADD MEMBER [$(AppUser)];
GO
