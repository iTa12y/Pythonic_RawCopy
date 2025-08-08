import os
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from helper import MFTEntry

ENTRY_SIZE = 1024
CHUNK_SIZE = 5000

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def read_buffer(chunk_data, start_index, count):
    entries = {}
    for i in range(count):
        try:
            offset = i * ENTRY_SIZE
            entry_data = chunk_data[offset:offset + ENTRY_SIZE]
            entry = MFTEntry(entry_data)
            if entry.is_valid():
                name, parent = entry.get_filename()
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
    
    logger.info(f"Looking for file: {target_path}")
    id_to_entry = {}

    with open(image_path, 'rb') as f:
        base_offset = int(mft_cluster) * int(cluster_size)
        max_entries = 2000000
        chunks = [(i, min(CHUNK_SIZE, max_entries - i)) for i in range(0, max_entries, CHUNK_SIZE)]
        
        with ThreadPoolExecutor(max_workers=4) as exe:
            futures = []
            for chunk_start, chunk_size in chunks:
                f.seek(base_offset + (chunk_start * ENTRY_SIZE))
                chunk_data = f.read(chunk_size * ENTRY_SIZE)
                future = exe.submit(read_buffer, chunk_data, chunk_start, chunk_size)
                futures.append(future)
            
            for future in as_completed(futures):
                try:
                    entries = future.result()
                    id_to_entry.update(entries)
                except Exception as e:
                    continue

    logger.info(f"Parsed {len(id_to_entry)} valid MFT entries")
    # First: find the MFT record for the target path
    target_id = None
    for idx, (name, parent, entry_data) in id_to_entry.items():
          if entry_data is None:
                continue
          full_path = build(idx, id_to_entry).lower()
          if full_path == target_path:
                target_id = idx
                entry = MFTEntry(entry_data, cluster_size)
                if entry.is_directory():
                          logger.info(f"Directory match found at record {idx}")
                else:
                          logger.info(f"File match found at record {idx}")
                break
    
    if target_id is None:
          raise FileNotFoundError(f"Path '{target_path}' not found in MFT")
        
    entry_data = id_to_entry[target_id][2]
    if entry_data is None:
          logger.error(f"Entry data for target_id {target_id} is None!")
          return None
    
    entry = MFTEntry(entry_data, cluster_size)
    if entry.is_directory():
      children = collect(target_id, id_to_entry, cluster_size)
      logger.debug(f"Found {len(children)} children under '{target_path}' (recursive)")
      return children
    return entry