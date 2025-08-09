import os
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from helper import MFTEntry

ENTRY_SIZE = 1024
CHUNK_SIZE = 5000

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def read_buffer(chunk_data, start_index, count, cluster_size):
    entries = {}
    for i in range(count):
        try:
            offset = i * ENTRY_SIZE
            entry_data = chunk_data[offset:offset + ENTRY_SIZE]
            entry = MFTEntry(entry_data, cluster_size)
            if entry.is_valid():
                name, parent = entry.filename()
                entries[start_index + i] = (name, parent, entry_data)
        except:
            continue
    return entries

def build(entry_id, id_to_entry):
    parts = []
    while entry_id in id_to_entry:
        name, parent, _ = id_to_entry[entry_id]
        if parent == entry_id or parent not in id_to_entry:
            break  # reached root
        parts.append(name)
        entry_id = parent
    return '/' + '/'.join(reversed(parts))

def collect(parent_id, id_to_entry, cluster_size):
    collected = []
    for idx, (name, parent, entry_data) in id_to_entry.items():
        if parent == parent_id:
            entry = MFTEntry(entry_data, cluster_size)
            full_path = build(idx, id_to_entry)
            if entry.is_directory():
                # It's a directory: collect its children recursively
                children = collect(idx, id_to_entry, cluster_size)
                collected.append((full_path, entry, children))
            else:
                collected.append((full_path, entry))   
    return collected
    
def scan(image_path, cluster_size, mft_cluster, target_path):
    target_path = os.path.abspath(target_path).replace('\\', '/').lower()
    target_path = re.sub(r'^[a-z]:', '', target_path)
    target_filename = os.path.basename(target_path).lower()
    logger.info(f"Looking for file: {target_path}")
    id_to_entry = {}
    
    with open(image_path, 'rb') as f:
        base_offset = int(mft_cluster) * int(cluster_size)
        max_entries = 2000000
        chunks = [(i, min(CHUNK_SIZE, max_entries - i)) for i in range(0, max_entries, CHUNK_SIZE)]     
        
        # Read all chunks first
        chunk_data_list = []
        for chunk_start, chunk_size in chunks:
            f.seek(base_offset + (chunk_start * ENTRY_SIZE))
            chunk_data = f.read(chunk_size * ENTRY_SIZE)
            chunk_data_list.append((chunk_data, chunk_start, chunk_size))
        
        # Process chunks in parallel
        with ThreadPoolExecutor(max_workers=min(8, len(chunks))) as exe:
            futures = [exe.submit(read_buffer, chunk_data, chunk_start, chunk_size, cluster_size) 
                      for chunk_data, chunk_start, chunk_size in chunk_data_list]
            
            for future in as_completed(futures):
                try:
                    id_to_entry.update(future.result())
                except:
                    continue
    
    logger.info(f"Parsed {len(id_to_entry)} valid MFT entries")  
    
    # Find the target path
    for idx, (name, _, entry_data) in id_to_entry.items():
        if entry_data is None:
            continue
        full_path = build(idx, id_to_entry).lower()
        if full_path == target_path:
            entry = MFTEntry(entry_data, cluster_size)
            if entry.is_directory():
                logger.info(f"Directory match found at record {idx}")
                children = collect(idx, id_to_entry, cluster_size)
                logger.info(f"Found {len(children)} children under '{target_path}' (recursive)")
                return children
            elif name.lower() == target_filename and entry.is_deleted():
                logger.info(f"Found deleted file '{name}' at record {idx} (possible match)")
                return entry         
            else:
                logger.info(f"File match found at record {idx}")
                return entry
        
    raise FileNotFoundError(f"Path '{target_path}' not found in MFT")


def write(output_dir, item, base_path):
    path = item[0]
    entry = item[1]
    
    # Create relative path once
    rel_path = os.path.relpath(path, start=base_path).replace('/', os.sep)
    out_path = os.path.join(output_dir, rel_path)
    
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
            write(output_dir, child, base_path)