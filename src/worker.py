import os
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from helper import MFTEntry

ENTRY_SIZE = 1024
CHUNK_SIZE = 5000

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def read_buffer(data, idx, c, cls):
    entries = {}
    for i in range(c):
        offset = i * ENTRY_SIZE
        entry_data = data[offset:offset + ENTRY_SIZE]
        entry = MFTEntry(entry_data, cls)
        if entry.is_deleted() or entry.is_valid():
            name, parent = entry.filename()
            entries[idx + i] = (name, parent, entry_data)
    return entries

def build(id, id_to_entry):
    parts = []
    while id in id_to_entry:
        name, parent, _ = id_to_entry[id]
        if parent == id or parent not in id_to_entry:
            break  # reached root
        parts.append(name)
        id = parent
    return '/' + '/'.join(reversed(parts))

def collect(pid, id_to_entry, cls):
    collected = []
    for idx, (name, parent, entry_data) in id_to_entry.items():
        if parent == pid:
            entry = MFTEntry(entry_data, cls)
            full_path = build(idx, id_to_entry)
            if entry.is_directory():
                # It's a directory: collect its children recursively
                children = collect(idx, id_to_entry, cls)
                collected.append((full_path, entry, children))
            else:
                collected.append((full_path, entry))   
    return collected
    
def scan(vol, cls, mft, path, recover_deleted=False):
    logger.info(f"Looking for file: {path}")
    id_to_entry = {}
    deleted_matches = []
    
    with open(vol, 'rb') as f:
        base_offset = int(mft) * int(cls)
        max_entries = 2000000
        chunks = [(i, min(CHUNK_SIZE, max_entries - i)) for i in range(0, max_entries, CHUNK_SIZE)]     
        
        chunk_data_list = []
        for chunk_start, chunk_size in chunks:
            f.seek(base_offset + (chunk_start * ENTRY_SIZE))
            chunk_data = f.read(chunk_size * ENTRY_SIZE)
            chunk_data_list.append((chunk_data, chunk_start, chunk_size))
        
        with ThreadPoolExecutor(max_workers=min(8, len(chunks))) as exe:
            futures = [exe.submit(read_buffer, chunk_data, chunk_start, chunk_size, cls) 
                      for chunk_data, chunk_start, chunk_size in chunk_data_list]
            
            for future in as_completed(futures):
                id_to_entry.update(future.result())
    
    logger.info(f"Parsed {len(id_to_entry)} valid MFT entries")
    
    if not path:
        output_file = "deleted_filenames.txt"
        with open(output_file, "w", encoding="utf-8") as out:
            for idx, (name, _, entry_data) in id_to_entry.items():
                entry = MFTEntry(entry_data, cls)
                if entry.is_deleted():
                    if entry.filename()[0] != "Unknown" and entry.filename()[0] is not None:
                        out.write(entry.filename()[0] + "\n")
        logger.info(f"All deleted filenames have been listed in {output_file}")
        return

    target_filename = os.path.basename(path).lower()
    if not recover_deleted:
        # Normal file search with full path
        path = os.path.abspath(path).replace('\\', '/').lower()
        path = re.sub(r'^[a-z]:', '', path)
        
        for idx, (name, _, entry_data) in id_to_entry.items():
            if entry_data is None:
                continue
                
            full_path = build(idx, id_to_entry).lower()
            entry = MFTEntry(entry_data, cls)
            
            if full_path == path:
                if entry.is_directory():
                    logger.info(f"Directory match found at record {idx}")
                    children = collect(idx, id_to_entry, cls)
                    logger.info(f"Found {len(children)} children under '{path}' (recursive)")
                    return children
                else:
                    logger.info(f"File match found at record {idx}")
                    return entry
    else:
        # Deleted file search by filename only
        for idx, (name, _, entry_data) in id_to_entry.items():
            if entry_data is None:
                continue
                
            entry = MFTEntry(entry_data, cls)
            if entry.is_deleted() and name.lower() == target_filename:
                full_path = build(idx, id_to_entry).lower()
                logger.info(f"Found deleted file '{name}' at record {idx}")
                deleted_matches.append((entry, full_path))

        if deleted_matches:
            logger.info(f"Found {len(deleted_matches)} deleted instances of '{target_filename}'")
            return sorted(deleted_matches, key=lambda x: x[1])
            
    raise FileNotFoundError(f"{'File' if not recover_deleted else 'Deleted file'} '{target_filename}' not found in MFT")


def write(output, item, path):
    path = item[0]
    entry = item[1]
    
    # Create relative path once
    rel_path = os.path.relpath(path, start=path).replace('/', os.sep)
    out_path = os.path.join(output, rel_path)
    
    if len(item) == 2:  # File
        data = entry.raw_data()
        if not data:
            logger.error(f"Failed to read file data for {os.path.basename(path)} it might be empty or corrupted, skipping.")
            return
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(data)
    else:  # Directory (len == 3)
        os.makedirs(out_path, exist_ok=True)
        for child in item[2]:  # children
            write(output, child, path)