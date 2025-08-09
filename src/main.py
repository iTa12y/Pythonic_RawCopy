import os
import argparse
from worker import scan, logger, write
from helper import BootSector, MFTEntry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy file from NTFS image using MFT")
    parser.add_argument("--volume", help="Volume to scan, e.g. '\\\\.\\C:', Or a path to an NTFS image file.")
    parser.add_argument("--file_path", help="Path to the file in NTFS to extract")
    parser.add_argument("--output_dir", help="Directory to write the output")
    args = parser.parse_args()

    bs = BootSector()
    boot_info = bs.read(args.volume)

    logger.info(f"Using cluster_size={int(boot_info['cls'])}, mft_cluster={int(boot_info['mft'])}")

    res = scan(args.volume, int(boot_info['cls']), int(boot_info['mft']), args.file_path)

    if isinstance(res, list):
        base_path = args.file_path.replace('\\', '/')
        base_folder_name = os.path.basename(base_path.rstrip("/\\"))
        target_root = os.path.join(args.output_dir, base_folder_name)
        os.makedirs(target_root, exist_ok=True) 
        write(target_root, (base_path, None, res), base_path)

    else:
        entry = MFTEntry(res.data, int(boot_info['cls']))
        filename = entry.filename()[0]
        data = entry.raw_data()
        if not data:
            logger.error("Failed to read file data")
        

    out_path = os.path.join(args.output_dir, filename)   
    with open(out_path, 'wb') as f:
        f.write(data)

    logger.info(f"File written to: {out_path}")
        