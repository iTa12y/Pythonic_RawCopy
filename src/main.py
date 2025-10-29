import os
import argparse
from worker import scan, logger, write
from helper import BootSector, MFTEntry

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copy file from NTFS image using MFT")
    parser.add_argument("--volume", help="Volume to scan, e.g. '\\\\.\\C:', Or a path to an NTFS image file.")
    parser.add_argument("--file_path", help="Path to the file in NTFS to extract")
    parser.add_argument("--output_dir", help="Directory to write the output")
    parser.add_argument("--recover-deleted", action="store_true", help="Search for and recover deleted files")
    parser.add_argument("--pid", type=int, help="Parent directory ID for more precise deleted file recovery")
    args = parser.parse_args()
    bs = BootSector()
    boot_info = bs.read(args.volume)
    logger.info(f"Using cluster_size={int(boot_info['cls'])}, mft_cluster={int(boot_info['mft'])}")
    res = scan(args.volume, int(boot_info['cls']), int(boot_info['mft']), args.file_path, args.recover_deleted, args.pid)
    if not args.file_path:
        exit(0)
    if res is None:
        logger.info("Deleted file scan completed, no single entry returned.")
        exit(0)
    if isinstance(res, list):
        if args.recover_deleted and len(res) > 0 and isinstance(res[0], tuple) and isinstance(res[0][0], MFTEntry):
            logger.info(f"Recovering {len(res)} deleted instances...")
            for idx, (entry, full_path) in enumerate(res):
                data = entry.raw_data(args.volume)
                if not data:
                    logger.warning(f"Failed to read data for deleted file at {full_path}")
                    continue
                base_name = os.path.basename(args.file_path)
                name, ext = os.path.splitext(base_name)
                recovery_name = f"{name}_recovered_{idx+1}{ext}"
                out_path = os.path.join(args.output_dir, recovery_name)      
                with open(out_path, 'wb') as f:
                    f.write(data)
                logger.info(f"Recovered file written to: {out_path}")
                
        else:
            base_path = args.file_path.replace('\\', '/')
            base_folder_name = os.path.basename(base_path.rstrip("/\\"))
            target_root = os.path.join(args.output_dir, base_folder_name)
            os.makedirs(target_root, exist_ok=True) 
            write(target_root, (base_path, None, res), base_path)
    else:
        entry = res if isinstance(res, MFTEntry) else MFTEntry(res.data, int(boot_info['cls']))
        filename = entry.filename()[0]
        data = entry.raw_data(args.volume)
        if not data:
            logger.error("Failed to read file data")
            exit(1)
        
        out_path = os.path.join(args.output_dir, filename)   
        with open(out_path, 'wb') as f:
            f.write(data)
        logger.info(f"File written to: {out_path}")