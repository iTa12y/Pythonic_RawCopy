# NTFS MFT File Extractor

A Python tool to locate and extract files directly from an NTFS volume image using the Master File Table (MFT). This utility parses raw MFT entries to reconstruct file paths and extract file contents without mounting the volume.

---

## Features

- Parses the NTFS MFT directly from a raw volume (e.g., `\\.\C:`).
- Multithreaded MFT entry parsing for performance.
- Reconstructs full file paths from MFT parent-child relationships.
- Supports extracting both resident and non-resident file data.
- Handles both long and short file names for accurate path resolution.
- Provides detailed debug output to trace the extraction process.

---

## Requirements

- Python 3.10+
- Runs on Windows (requires access to NTFS volume devices, e.g., `\\.\C:`)

---

## Installation

Clone the repository or download the source files:

```bash
git clone https://github.com/yourusername/ntfs-mft-extractor.git
cd ntfs-mft-extractor
