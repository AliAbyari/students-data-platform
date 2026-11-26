SET NOCOUNT ON;

IF DB_ID(N'StudentsPortal') IS NULL
    CREATE DATABASE StudentsPortal;
GO
USE StudentsPortal;
GO
IF SCHEMA_ID(N'app') IS NULL
    EXEC (N'CREATE SCHEMA app AUTHORIZATION dbo');
GO
IF OBJECT_ID(N'app.Users') IS NULL
CREATE TABLE app.Users (
    UserId            int IDENTITY(1, 1) NOT NULL CONSTRAINT PK_Users PRIMARY KEY,
    Username          nvarchar(64)   NOT NULL CONSTRAINT UQ_Users_Username UNIQUE,
    PasswordHash      nvarchar(400)  NOT NULL,
    FirstName         nvarchar(64)   NOT NULL,
    LastName          nvarchar(64)   NOT NULL,
    Email             nvarchar(128)  NULL,
    [Role]            varchar(16)    NOT NULL CONSTRAINT CK_Users_Role CHECK ([Role] IN ('Admin', 'User')),
    IsActive          bit            NOT NULL CONSTRAINT DF_Users_IsActive DEFAULT 1,
    PreferredLanguage char(2)        NOT NULL CONSTRAINT DF_Users_Language DEFAULT 'fa'
                                     CONSTRAINT CK_Users_Language CHECK (PreferredLanguage IN ('fa', 'en')),
    PreferredTheme    varchar(8)     NOT NULL CONSTRAINT DF_Users_Theme DEFAULT 'light'
                                     CONSTRAINT CK_Users_Theme CHECK (PreferredTheme IN ('dark', 'light')),
    SessionStamp      uniqueidentifier NOT NULL CONSTRAINT DF_Users_SessionStamp DEFAULT NEWID(),
    CreatedAt         datetime2(0)   NOT NULL CONSTRAINT DF_Users_CreatedAt DEFAULT SYSUTCDATETIME(),
    LastLoginAt       datetime2(0)   NULL
);
GO
IF EXISTS (SELECT 1 FROM sys.default_constraints
           WHERE name = N'DF_Users_Theme' AND definition <> N'(''light'')')
BEGIN
    ALTER TABLE app.Users DROP CONSTRAINT DF_Users_Theme;
    ALTER TABLE app.Users ADD CONSTRAINT DF_Users_Theme DEFAULT 'light' FOR PreferredTheme;
END
GO
IF OBJECT_ID(N'app.ActivityLog') IS NULL
CREATE TABLE app.ActivityLog (
    ActivityId  bigint IDENTITY(1, 1) NOT NULL CONSTRAINT PK_ActivityLog PRIMARY KEY,
    UserId      int            NULL,
    Action      varchar(32)    NOT NULL,
    Entity      varchar(64)    NOT NULL,
    EntityKey   nvarchar(64)   NULL,
    OccurredAt  datetime2(3)   NOT NULL CONSTRAINT DF_ActivityLog_OccurredAt DEFAULT SYSUTCDATETIME()
);
GO
