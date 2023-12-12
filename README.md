## raw_report.sh
This script will generate a text file, `disk_report_YYYY-MM-DD`, summarizing each sub-directory in a specified directory and a symbolic link to this file named `disk_report_latest`. It will list the number and total size of files in each sub-directory, organized by user ownership.
The script needs to be run with sudo.

```
sudo ./raw_report.sh <root-dir> <threads>
```

## disk_report.py
This script aggregates the file created by [raw_report.sh](/raw_report.sh) and creates a human-readable form per each user and for all users.

Usage example:
```
python3 disk_report.py --infile p33-disk_report_2023-11-22 --out p33_filetree
```
