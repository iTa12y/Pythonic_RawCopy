from dataclasses import dataclass

@dataclass
class BootSector:
    bps: int = 0
    spc: int = 0
    cls: int = 0
    mft: int = 0

    def read(self, vol: str) -> dict:
        with open(vol, "rb") as f:
            boot = f.read(512)
        self.bps = int.from_bytes(boot[11:13], 'little')
        self.spc = boot[13]
        self.cls = self.bps * self.spc
        self.mft = int.from_bytes(boot[48:56], 'little')
        return {"cls": self.cls, "mft": self.mft}

@dataclass
class MFTEntry:
    data: bytes
    cluster_size: int = 4096

    def _flags(self) -> int:
        return int.from_bytes(self.data[22:24], 'little')

    def is_valid(self) -> bool:
        return self.data.startswith(b'FILE')

    def is_deleted(self) -> bool:
        return not (self._flags() & 0x01)

    def is_directory(self) -> bool:
        return bool(self._flags() & 0x02)

    def filename(self) -> tuple[str, int | None]:
        name, parent_ref = "Unknown", None
        offset = int.from_bytes(self.data[20:22], 'little')
        while offset < 1024:
            try:
                attr_type = int.from_bytes(self.data[offset:offset+4], 'little')
                if attr_type == 0xFFFFFFFF:
                    break
                if attr_type == 0x30:  # FILE_NAME attribute
                    parent_ref = int.from_bytes(self.data[offset+24:offset+30], 'little') & 0xFFFFFFFFFFFF
                    name_len, ns = self.data[offset+88], self.data[offset+89]
                    if name == "Unknown" or ns in (0x00, 0x03):  # Prefer Win32 names
                        name = self.data[offset+90:offset+90+(name_len*2)].decode('utf-16le', 'replace')
                        if ns in (0x00, 0x03):
                            break
                offset += int.from_bytes(self.data[offset+4:offset+8], 'little') or 1024
            except Exception:
                break
        return name, parent_ref

    def raw_data(self, vol: str) -> bytes:
        offset = int.from_bytes(self.data[20:22], 'little')
        with open(vol, 'rb') as f:
            while offset < 1024:
                attr_type = int.from_bytes(self.data[offset:offset+4], 'little')
                if attr_type in (0xFFFFFFFF, 0):
                    break
                if attr_type == 0x80:  # DATA attribute
                    non_res = self.data[offset+8]
                    if not non_res:  # Resident
                        size = int.from_bytes(self.data[offset+16:offset+20], 'little')
                        off = int.from_bytes(self.data[offset+20:offset+22], 'little')
                        return self.data[offset+off:offset+off+size]
                    
                    run_off = int.from_bytes(self.data[offset+32:offset+34], 'little')
                    size = int.from_bytes(self.data[offset+48:offset+56], 'little')
                    data, cur, abs_cluster = bytearray(), offset + run_off, 0
                    while cur < 1024:
                        hdr = self.data[cur]
                        if not hdr:
                            break
                        len_sz, off_sz = hdr & 0xF, hdr >> 4
                        cur += 1
                        run_len = int.from_bytes(self.data[cur:cur+len_sz], 'little')
                        cur += len_sz
                        run_off = int.from_bytes(self.data[cur:cur+off_sz], 'little', signed=True)
                        cur += off_sz
                        abs_cluster += run_off
                        f.seek(abs_cluster * self.cluster_size)
                        data.extend(f.read(run_len * self.cluster_size))
                        if len(data) >= size:
                            return bytes(data[:size])
                offset += int.from_bytes(self.data[offset+4:offset+8], 'little') or 1024
        return b''
