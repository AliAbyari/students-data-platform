SET NOCOUNT ON;

DECLARE @files TABLE (
    LogicalName nvarchar(128), PhysicalName nvarchar(260), [Type] char(1), FileGroupName nvarchar(128),
    Size numeric(20, 0), MaxSize numeric(20, 0), FileId bigint, CreateLSN numeric(25, 0), DropLSN numeric(25, 0),
    UniqueId uniqueidentifier, ReadOnlyLSN numeric(25, 0), ReadWriteLSN numeric(25, 0), BackupSizeInBytes bigint,
    SourceBlockSize int, FileGroupId int, LogGroupGUID uniqueidentifier, DifferentialBaseLSN numeric(25, 0),
    DifferentialBaseGUID uniqueidentifier, IsReadOnly bit, IsPresent bit, TDEThumbprint varbinary(32),
    SnapshotUrl nvarchar(360));

INSERT INTO @files EXEC (N'RESTORE FILELISTONLY FROM DISK = N''/backup/Students.bak''');

DECLARE @move nvarchar(max) = N'';
SELECT @move += N', MOVE N''' + LogicalName + N''' TO N''/var/opt/mssql/data/Students_' + CAST(FileId AS nvarchar(10))
             + CASE [Type] WHEN 'L' THEN N'.ldf' WHEN 'D' THEN N'.mdf' ELSE N'.ndf' END + N''''
FROM @files;

DECLARE @sql nvarchar(max) = N'RESTORE DATABASE Students FROM DISK = N''/backup/Students.bak'' WITH RECOVERY, REPLACE, STATS = 10'
                             + @move + N';';
EXEC (@sql);

ALTER DATABASE Students SET RECOVERY SIMPLE;
ALTER AUTHORIZATION ON DATABASE::Students TO sa;
