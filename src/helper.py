from dataclasses import dataclass

@dataclass
class BootSector:
    bps: int = 0
    spc: int = 0
    cls: int = 0
    mft: int = 0
    
    def read(self, vol) -> dict:
        with open(vol, "rb") as f:
            boot = f.read(512)
            self.bps = int.from_bytes(boot[11:13], 'little')
            self.spc = boot[13]
            self.cls = self.bps * self.spc
            self.mft = int.from_bytes(boot[48:56], 'little')
            return {"bps": self.bps, "spc": self.spc, "cls": self.cls, "mft": self.mft}

@dataclass
class MFTEntry:
    data: bytes
    cluster_size: int = 4096
    
    def is_valid(self) -> bool: return self.data[0:4] == b'FILE'

    def is_deleted(self) -> bool: return not (int.from_bytes(self.data[22:24], 'little') & 0x01)
    
    def is_directory(self) -> bool: return (int.from_bytes(self.data[22:24], 'little') & 0x0002) != 0
    
    def filename(self) -> tuple[str, int]:
        offset = int.from_bytes(self.data[20:22], 'little')
        long_name = None
        short_name = None
        parent_ref = None

        while offset < 1024:
            try:
                attr_type = int.from_bytes(self.data[offset:offset+4], 'little')

                if attr_type == 0x30:  # FILE_NAME attribute
                    parent_ref = int.from_bytes(self.data[offset+24:offset+30], 'little') & 0xFFFFFFFFFFFF
                    name_length = self.data[offset+88]
                    name_space = self.data[offset+89]
                    name_offset = offset + 90

                    name_bytes = self.data[name_offset:name_offset + (name_length * 2)]
                    current_name = name_bytes.decode('utf-16le', errors='replace')

                    if name_space == 0x01:
                        # DOS short name
                        short_name = current_name
                    elif name_space in (0x00, 0x03):
                        # Win32 or Win32+DOS long name
                        if not long_name:
                            long_name = current_name

                elif attr_type == 0xFFFFFFFF:
                    break

                attr_len = int.from_bytes(self.data[offset+4:offset+8], 'little')
                if attr_len == 0:
                    break
                offset += attr_len

            except Exception:
                break

        return (long_name or short_name or "Unknown", parent_ref)

    def raw_data(self) -> bytes:
        offset = int.from_bytes(self.data[20:22], 'little')
        
        while offset < 1024:
            attr_type = int.from_bytes(self.data[offset:offset+4], 'little')
            
            if attr_type == 0x80:
                non_res_flag = self.data[offset + 8]
                
                if non_res_flag == 0:
                    content_size = int.from_bytes(self.data[offset+16:offset+20], 'little')
                    content_offset = int.from_bytes(self.data[offset+20:offset+22], 'little')
                    return self.data[offset + content_offset:offset + content_offset + content_size]
                
                else:
                    # Get data runs offset and size
                    run_offset = int.from_bytes(self.data[offset+32:offset+34], 'little')
                    data_size = int.from_bytes(self.data[offset+48:offset+56], 'little')
                    
                    # Parse data runs
                    current_offset = offset + run_offset
                    data = bytearray()
                    absolute_cluster = 0
                    
                    with open(r'\\.\C:', 'rb') as f:
                        while current_offset < 1024:
                            header = self.data[current_offset]
                            if header == 0:
                                break
                            
                            length_size = header & 0x0F
                            offset_size = (header >> 4) & 0x0F
                            current_offset += 1
                            
                            if length_size == 0 or offset_size == 0:
                                break
                            
                            # Read the length
                            run_length = int.from_bytes(self.data[current_offset:current_offset + length_size], 'little')
                            current_offset += length_size
                            
                            # Read the offset 
                            offset_bytes = self.data[current_offset:current_offset + offset_size]
                            run_offset = int.from_bytes(offset_bytes, 'little', signed=True)
                            current_offset += offset_size
                            
                            absolute_cluster += run_offset
                            
                            f.seek(absolute_cluster * self.cluster_size)
                            data.extend(f.read(run_length * self.cluster_size))
                            
                            if len(data) >= data_size:
                                return bytes(data[:data_size])
                            
            elif attr_type == 0xFFFFFFFF:
                break
            
            attr_len = int.from_bytes(self.data[offset+4:offset+8], 'little')
            if attr_len == 0:
                break
            offset += attr_len
            
        return b''