# Pythonic_RawCopy

A Python-based forensic tool for NTFS file system analysis and recovery. This utility directly reads and parses the Master File Table (MFT) to locate, extract, and recover files from NTFS volumes or raw disk images without mounting them.

## Features

- **Direct MFT Access**: Parse NTFS MFT entries from raw volumes (`\\.\C:`) or disk images
- **File Recovery**: Recover deleted files using MFT entry data
- **Path Reconstruction**: Rebuild complete file paths from MFT parent-child relationships
- **Multi-threaded**: Parallel processing of MFT entries for enhanced performance
- **Flexible Operation Modes**:
  - List all deleted files on a volume
  - Extract specific files by path
  - Recover deleted files
  - Handle both resident and non-resident file data

## Requirements

- Python 3.10+
- Windows operating system
- Administrative privileges (for raw volume access) or raw disk image

## Installation

1. Clone the repository:
```bash
git clone https://github.com/iTa12y/Pythonic_RawCopy.git
cd Pythonic_RawCopy
```

## Usage

### List All Deleted Files
```bash
python src/main.py --volume \\.\C:
```

### Extract Specific File or Directory
```bash
python src/main.py --volume \\.\C: --file_path path/to/file.txt --output_dir ./output
```

### Recover Deleted File
```bash
python src/main.py --volume \\.\C: --file_path filename.txt --output_dir ./recovered --recover-deleted 
```

## Command Line Arguments

- `--volume`: NTFS volume to scan (e.g., `\\.\C:`) or path to raw image
- `--file_path`: Path to file for extraction (optional)
- `--output_dir`: Directory for output files
- `--recover-deleted`: Enable deleted file recovery mode

## Output Format

When listing deleted files, the tool creates a formatted text file containing:
- Full original path (if available)
- Filename
- MFT record number

## Limitations

- Requires administrative privileges for raw volume access
- Recovery success depends on whether file data has been overwritten
- Some deleted files may have incomplete path information

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Based on NTFS file system specifications
- Inspired by various forensic analysis tools