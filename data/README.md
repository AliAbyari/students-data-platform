`Students.bak.tar.gz.001` ... `.005` are the parts of the compressed backup of the operational `Students` database (SQL Server).
`start.sh` / `start.bat` unpack it to `Students.bak` on the first run; SQL Server restores it
from there (the folder is mounted read-only at /backup). The unpacked file is not versioned.
