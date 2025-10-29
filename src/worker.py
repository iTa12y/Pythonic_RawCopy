import os
import re
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from helper import MFTEntry

ENTRY_SIZE = 1024
CHUNK_SIZE = 5000
MAX_ENTRIES = 2_000_000

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def iter_mft_entries(volume, base_offset, cls):
    with open(volume, 'rb') as f:
        for i in range(MAX_ENTRIES):
            f.seek(base_offset + i * ENTRY_SIZE)
            data = f.read(ENTRY_SIZE)
            if len(data) < ENTRY_SIZE:
                break
            entry = MFTEntry(data, cls)
            if not (entry.is_valid() or entry.is_deleted()):
                continue
            name, parent = entry.filename()
            if name and parent is not None:
                yield i, name, parent, entry

def parallel_entries(volume, base_offset, cls):
    def parse_chunk(start, count):
        results = []
        with open(volume, 'rb') as f:
            f.seek(base_offset + start * ENTRY_SIZE)
            chunk = f.read(count * ENTRY_SIZE)
            for i in range(count):
                entry_data = chunk[i * ENTRY_SIZE:(i + 1) * ENTRY_SIZE]
                entry = MFTEntry(entry_data, cls)
                if not (entry.is_valid() or entry.is_deleted()):
                    continue
                name, parent = entry.filename()
                if name and parent is not None:
                    results.append((start + i, name, parent, entry))
        return results

    chunks = [(i, min(CHUNK_SIZE, MAX_ENTRIES - i)) for i in range(0, MAX_ENTRIES, CHUNK_SIZE)]
    with ThreadPoolExecutor(max_workers=8) as exe:
        for future in as_completed([exe.submit(parse_chunk, s, c) for s, c in chunks]):
            for item in future.result():
                yield item

def build_path(fid, lookup):
    parts = []
    while fid in lookup:
        name, parent = lookup[fid]
        if parent == fid or parent not in lookup:
            break
        parts.append(name)
        fid = parent
    return '/' + '/'.join(reversed(parts))

def collect_children(pid, lookup, cls):
    for fid, (name, parent, entry) in lookup.items():
        if parent == pid:
            full_path = build_path(fid, {k: (v[0], v[1]) for k, v in lookup.items()})
            yield (full_path, entry, list(collect_children(fid, lookup, cls))) if entry.is_directory() else(full_path, entry)

def scan(volume, cls, mft_offset, path, recover_deleted=False, pid=None):
    logger.info(f"Scanning for: {path or 'deleted files'}")
    base_offset = int(mft_offset) * int(cls)
    entries = {i: (n, p, e) for i, n, p, e in parallel_entries(volume, base_offset, cls)}
    logger.info(f"Parsed {len(entries)} valid MFT entries")

    if not path:
        out_file = "deleted_filenames.txt"
        with open(out_file, "w", encoding="utf-8") as out:
            for name, parent, entry in (v for v in entries.values() if v[2].is_deleted()):
                if name not in (None, "Unknown"):
                    out.write(f"{name},{parent}\n")
                    out.close()
        logger.info(f"Deleted filenames written to {out_file}")
        return

    target = os.path.basename(path).lower()
    norm_path = re.sub(r'^[a-z]:', '', os.path.abspath(path).replace('\\', '/').lower())

    if not recover_deleted:
        for fid, (name, parent, entry) in entries.items():
            if build_path(fid, {k: (v[0], v[1]) for k, v in entries.items()}).lower() == norm_path:
                if entry.is_directory():
                    children = list(collect_children(fid, entries, cls))
                    logger.info(f"Directory found at record {fid} with {len(children)} children")
                    return children
                logger.info(f"File match found at record {fid}")
                return entry
    else:
        deleted = [
            (entry, build_path(fid, {k: (v[0], v[1]) for k, v in entries.items()}).lower())
            for fid, (name, parent, entry) in entries.items()
            if entry.is_deleted()
            and name.lower() == target
            and (pid is None or (parent & 0xFFFFFFFFFFFF) == pid)
        ]
        if deleted:
            logger.info(f"Found {len(deleted)} deleted instance(s) of '{target}'")
            return sorted(deleted, key=lambda x: x[1])

    raise FileNotFoundError(f"{'Deleted file' if recover_deleted else 'File'} '{target}' not found")

def write(output_dir, item, base_path):
    path, entry, *children = item
    rel_path = os.path.relpath(path, start=base_path).replace('/', os.sep)
    out_path = os.path.join(output_dir, rel_path)
    if not children:  # File
        data = entry.raw_data()
        if not data:
            logger.warning(f"Skipping empty/corrupted file {os.path.basename(path)}")
            return
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'wb') as f:
            f.write(data)
    else:  # Directory
        os.makedirs(out_path, exist_ok=True)
        for child in children[0]:
            write(output_dir, child, base_path)
