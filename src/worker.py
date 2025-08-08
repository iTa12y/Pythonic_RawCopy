import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from helper import MFTEntry

ENTRY_SIZE = 1024
CHUNK_SIZE = 5000 

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

def build_full_path(entry_id, id_to_entry):
    parts = []
    while entry_id in id_to_entry:
        name, parent, _ = id_to_entry[entry_id]
        if parent == entry_id or parent not in id_to_entry:
            break  # reached root
        parts.append(name)
        entry_id = parent
    return '/' + '/'.join(reversed(parts))

def scan_mft_for_path(image_path, cluster_size, mft_cluster, target_path):
    start_time = time.time()
    target_path = os.path.abspath(target_path).replace('\\', '/').lower()
    target_path = re.sub(r'^[a-z]:', '', target_path)
    
    print(f"[DEBUG] Looking for file: {target_path}")
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

    print(f"[DEBUG] Parsed {len(id_to_entry)} valid MFT entries")

    for idx, (name, parent, entry_data) in id_to_entry.items():
        full_path = build_full_path(idx, id_to_entry).lower()
        if full_path == target_path:
            elapsed = time.time() - start_time
            print(f"[DEBUG] MATCH FOUND! '{target_path}' at record {idx} in {elapsed:.2f} seconds")
            return MFTEntry(entry_data, cluster_size)


    elapsed = time.time() - start_time
    print(f"[DEBUG] Scan completed in {elapsed:.2f} seconds — No exact match found")
    raise FileNotFoundError(f"File '{target_path}' not found in MFT")


