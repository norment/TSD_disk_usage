## raw_report.sh
This script will generate a text file, `disk_report_YYYY-MM-DD`, summarizing each sub-directory in a specified directory and a symbolic link to this file named `disk_report_latest`. It will list the number and total size of files in each sub-directory, organized by user ownership.
The script needs to be run with sudo.

```
sudo ./raw_report.sh <root-dir> <threads>
```
