SET NOCOUNT ON;
USE Students;

IF (SELECT is_cdc_enabled FROM sys.databases WHERE name = N'Students') = 0
    EXEC sys.sp_cdc_enable_db;
GO

SET NOCOUNT ON;
DECLARE @table sysname;
DECLARE captured CURSOR LOCAL FAST_FORWARD FOR
    SELECT name FROM (VALUES (N'Students'), (N'CourseEnrollments'), (N'CourseOfferings'), (N'Applicants')) AS t (name);
OPEN captured;
FETCH NEXT FROM captured INTO @table;
WHILE @@FETCH_STATUS = 0
BEGIN
    IF NOT EXISTS (SELECT 1 FROM cdc.change_tables WHERE source_object_id = OBJECT_ID(N'dbo.' + @table))
        EXEC sys.sp_cdc_enable_table
             @source_schema        = N'dbo',
             @source_name          = @table,
             @role_name            = NULL,
             @supports_net_changes = 0;
    FETCH NEXT FROM captured INTO @table;
END;
CLOSE captured;
DEALLOCATE captured;

EXEC sys.sp_cdc_change_job @job_type = N'cleanup', @retention = 4320;

SET NOCOUNT ON;
DECLARE @job sysname = N'cdc.' + DB_NAME() + N'_capture';
DECLARE @running bit;
DECLARE @check nvarchar(max) = N'
    SELECT @running = CASE WHEN EXISTS (
        SELECT 1 FROM msdb.dbo.sysjobactivity AS a
        JOIN msdb.dbo.sysjobs AS j ON j.job_id = a.job_id
        WHERE j.name = @job AND a.start_execution_date IS NOT NULL AND a.stop_execution_date IS NULL
          AND a.session_id = (SELECT MAX(session_id) FROM msdb.dbo.syssessions)) THEN 1 ELSE 0 END;';

DECLARE @stopped bit = 0, @tries int = 0;
IF EXISTS (SELECT 1 FROM msdb.dbo.cdc_jobs WHERE database_id = DB_ID() AND job_type = N'capture' AND pollinginterval <> 1)
BEGIN
    EXEC sys.sp_cdc_change_job @job_type = N'capture', @pollinginterval = 1;
    EXEC sp_executesql @check, N'@job sysname, @running bit OUTPUT', @job, @running OUTPUT;
    IF @running = 1
    BEGIN
        EXEC msdb.dbo.sp_stop_job @job_name = @job;
        SET @stopped = 1;
    END;
END;

EXEC sp_executesql @check, N'@job sysname, @running bit OUTPUT', @job, @running OUTPUT;
WHILE @stopped = 1 AND @running = 1 AND @tries < 30
BEGIN
    WAITFOR DELAY '00:00:01';
    SET @tries += 1;
    EXEC sp_executesql @check, N'@job sysname, @running bit OUTPUT', @job, @running OUTPUT;
END;

IF @running = 0
    EXEC msdb.dbo.sp_start_job @job_name = @job;
