import os
import argparse
from worker import scan_mft_for_path
from helper import BootSector

def main():
    parser = argparse.ArgumentParser(description="Copy file from NTFS image using MFT")
    parser.add_argument("--file_path", help="Path to the file in NTFS to extract")
    parser.add_argument("--output_dir", help="Directory to write the output")
    args = parser.parse_args()
    
    bs = BootSector()
    vol = r'\\.\C:'
    boot_info = bs.read(vol)
    
    print(f"Using cluster_size={int(boot_info['cls'])}, mft_cluster={int(boot_info['mft'])}")
    
    entry = scan_mft_for_path(vol, int(boot_info['cls']), int(boot_info['mft']), args.file_path)

    filename = entry.get_filename()
    data = entry.get_file_raw_data()
    if not data:
        print("Failed to read file data")
        return

    out_path = os.path.join(args.output_dir, filename[0])
    print(f"Writing {len(data):,} bytes to {out_path}")
    
    with open(out_path, 'wb') as f:
        f.write(data)

    print(f"File written to: {out_path}")
    return

if __name__ == "__main__":
    main()