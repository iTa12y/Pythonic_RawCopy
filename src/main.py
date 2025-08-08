import os
import argparse
from worker import scan, logger
from helper import BootSector, MFTEntry

def write_entry(output_dir, item, base_path):
    if len(item) == 2:
        path, entry = item
        data = entry.get_file_raw_data()
        if not data:
            logger.error(f"Failed to read file data for {os.path.basename(path)} it might be empty or corrupted, skipping.")
            return
        # Make path relative to base_path, so nested structure is preserved properly
        rel_path = os.path.relpath(path, start=base_path).replace('/', os.sep)
        out_path = os.path.join(output_dir, rel_path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(data)
    elif len(item) == 3:
        path, entry, children = item
        rel_dir_path = os.path.relpath(path, start=base_path).replace('/', os.sep)
        dir_path = os.path.join(output_dir, rel_dir_path)
        os.makedirs(dir_path, exist_ok=True)
        for child in children:
            write_entry(output_dir, child, base_path)


def main():
    parser = argparse.ArgumentParser(description="Copy file from NTFS image using MFT")
    parser.add_argument("--file_path", help="Path to the file in NTFS to extract")
    parser.add_argument("--output_dir", help="Directory to write the output")
    args = parser.parse_args()
    
    bs = BootSector()
    vol = r'\\.\C:'
    boot_info = bs.read(vol)
    
    logger.info(f"Using cluster_size={int(boot_info['cls'])}, mft_cluster={int(boot_info['mft'])}")
    
    res = scan(vol, int(boot_info['cls']), int(boot_info['mft']), args.file_path)
    
    if isinstance(res, list):
      base_path = args.file_path.replace('\\', '/')
      base_folder_name = os.path.basename(base_path.rstrip("/\\"))
      target_root = os.path.join(args.output_dir, base_folder_name)
      os.makedirs(target_root, exist_ok=True) 
      write_entry(target_root, (base_path, None, res), base_path)
      
    else:
        entry = MFTEntry(res.data, int(boot_info['cls']))
        filename = entry.get_filename()[0]
        data = entry.get_file_raw_data()
        if not data:
            logger.error("Failed to read file data")
            return
        
        out_path = os.path.join(args.output_dir, filename)   
        with open(out_path, 'wb') as f:
            f.write(data)

        logger.info(f"File written to: {out_path}")
        return

if __name__ == "__main__":
    main()