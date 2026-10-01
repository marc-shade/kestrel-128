"""Independent Editor gap-buffer byte oracle for complete VICE REU snapshots."""
import hashlib

from hwlib import lst_symbol
from native_vdc_check import owned_service


class ReuHistoryOracle:
    """Expected edit payloads, independent of the allocator's chosen locations."""
    def __init__(self, memory):
        self.memory = memory
        self.entries = []
        self.cursor = self.saved = 0

    def clear(self, dirty=False):
        assert all('base' in entry for entry in self.entries), 'capture history before clearing it'
        self.entries = []
        self.cursor = 0
        self.saved = 255 if dirty else 0

    def save(self):
        self.saved = self.cursor

    def edit(self, position, removed, inserted):
        assert all('base' in entry for entry in self.entries[self.cursor:]), 'capture redo before discarding it'
        self.entries = self.entries[:self.cursor]
        if self.saved > self.cursor:
            self.saved = 255
        payload = (b''.join(value.to_bytes(3, 'little') for value in
                           (position, len(removed), len(inserted)))+removed+inserted)
        self.entries.append(dict(position=position, before=bytes(removed), after=bytes(inserted), payload=payload))
        if len(self.entries) > 16:
            assert 'base' in self.entries[0], 'capture every record before eviction'
            self.entries.pop(0)
            if self.saved != 255:
                self.saved = self.saved-1 if self.saved else 255
        self.cursor = len(self.entries)

    def replay(self, redo=False):
        if redo:
            assert self.cursor < len(self.entries)
            entry = self.entries[self.cursor]
            self.cursor += 1
            return entry['position'], len(entry['before']), entry['after']
        assert self.cursor
        self.cursor -= 1
        entry = self.entries[self.cursor]
        return entry['position'], len(entry['after']), entry['before']

    def capture(self, provider, records):
        assert provider('bh_count', 1) == bytes([len(self.entries)])
        assert provider('bh_cursor', 1) == bytes([self.cursor])
        assert provider('bh_saved', 1) == bytes([self.saved])
        assert provider('bh_pending', 1) == provider('bh_replay', 1) == b'\0'
        assert provider('bh_live', 1) == bytes([len(self.entries)])
        slots = provider('bh_records', 17*9)
        evidence = []
        for index, entry in enumerate(self.entries):
            slot = slots[index*9:index*9+9]
            assert slot[0] == 2
            token = slot[1:]
            assert 1 <= token[0] <= 32 and token[4:] == provider('ru_cookie', 4)
            record = records[(token[0]-1)*8:token[0]*8]
            assert record[0] == 33 and record[5:] == token[1:4]
            base = int.from_bytes(record[1:3], 'little')*4096
            capacity = int.from_bytes(record[3:5], 'little')*4096
            assert capacity == (len(entry['payload'])+4095)//4096*4096
            assert base+capacity <= len(self.memory)
            for other in range(0, len(records), 8):
                if other == (token[0]-1)*8 or not records[other]:
                    continue
                first = int.from_bytes(records[other+1:other+3], 'little')*4096
                length = int.from_bytes(records[other+3:other+5], 'little')*4096
                assert base+capacity <= first or first+length <= base
            if 'base' in entry:
                assert (entry['base'], entry['token']) == (base, token)
            else:
                entry.update(base=base, token=token, capacity=capacity)
                self.memory[base:base+len(entry['payload'])] = entry['payload']
            evidence.append(dict(index=index, token=token.hex(), record=record.hex(), base=base,
                                 capacity=capacity, payload_hex=entry['payload'].hex()))
        assert all(slots[index*9] == 0 for index in range(len(self.entries), 17))
        return dict(cursor=self.cursor, saved=self.saved, entries=evidence)

    def check_memory(self, actual):
        for entry in self.entries:
            first, last = entry['base'], entry['base']+entry['capacity']
            assert actual[first:last] == self.memory[first:last], 'complete history extent, including unused capacity'


class ReuDocumentOracle:
    def __init__(self, initial, history=False):
        self.expected = bytearray(initial)
        self.logical = b''
        self.base = self.capacity = self.gap = self.end = 0
        self.history = ReuHistoryOracle(self.expected) if history else None

    def insert(self, position, data, *, record=True):
        assert 0 <= position <= len(self.logical)
        assert len(data) <= self.end-self.gap
        if self.history and record and data:
            self.history.edit(position, b'', data)
        if position < self.gap:
            count = self.gap-position
            self.end -= count
            self.expected[self.base+self.end:self.base+self.end+count] = self.logical[position:self.gap]
        elif position > self.gap:
            count = position-self.gap
            self.expected[self.base+self.gap:self.base+position] = self.logical[self.gap:position]
            self.end += count
        self.expected[self.base+position:self.base+position+len(data)] = data
        self.gap = position+len(data)
        self.logical = self.logical[:position]+data+self.logical[position:]

    def replace(self, position, removed, data, *, record=True):
        assert 0 <= position <= len(self.logical) and 0 <= removed <= len(self.logical)-position
        assert len(data) <= self.end-self.gap+removed
        original = self.logical
        if self.history and record:
            self.history.edit(position, original[position:position+removed], data)
        self.insert(position, b'', record=False)
        self.expected[self.base+position:self.base+position+len(data)] = data
        self.gap = position+len(data)
        self.end += removed
        self.logical = original[:position]+data+original[position+removed:]

    def capture(self, capture, read_app, folder, label, snapshot, logical, *, loaded=False):
        symbol = lambda name: lst_symbol('native-desktop/editor', name)
        active = bytes(read_app(symbol('ed_active'), 1))[0]
        assert active in (0, 128)
        state = bytes(read_app(symbol('d_states')+active, 128))
        assert state[13:16] == bytes([1, 0, 1])
        token = state[16:24]
        assert 1 <= token[0] <= 32
        provider, code = owned_service(capture, read_app, folder, label, 'native-desktop/editor')
        assert provider('bm_lease', 1) == provider('ru_active', 1) == b'\1'
        assert token[4:] == provider('ru_cookie', 4)
        assert bytes(read_app(0x3860, 1)) == token[4:5]
        app = bytes(read_app(0x3c00+(token[4]-1)*8, 8))
        assert app[:3] == bytes([32, 0, 0x60]) and app[4:7] == token[5:]
        records = provider('ru_records', 256)
        history = self.history.capture(provider, records) if self.history else None
        at = (token[0]-1)*8
        record = records[at:at+8]
        assert record[0] == 33 and record[5:] == token[1:4]
        base = int.from_bytes(record[1:3], 'little')*4096
        capacity = int.from_bytes(record[3:5], 'little')*4096
        assert 0 < capacity and base+capacity <= len(self.expected)
        intervals = []
        for other in range(0, 256, 8):
            if other == at or not records[other]:
                continue
            first = int.from_bytes(records[other+1:other+3], 'little')*4096
            count = int.from_bytes(records[other+3:other+5], 'little')*4096
            assert base+capacity <= first or first+count <= base
            intervals.append((first, count))
        if loaded:
            assert capacity == (len(logical)+4095)//4096*4096
            # These workflows start from an empty document with only the
            # display snapshot allocated, then append the complete input.
            first_fit = next(start for start in range(0, len(self.expected)-capacity+1, 4096)
                             if all(start+capacity <= first or first+count <= start for first, count in intervals))
            assert base == first_fit
            self.base, self.capacity = base, capacity
            self.gap, self.end = len(logical), capacity
            self.logical = logical
            self.expected[base:base+len(logical)] = logical
        assert (base, capacity) == (self.base, self.capacity)
        assert logical == self.logical
        assert [int.from_bytes(state[i:i+3], 'little') for i in (0, 3, 6, 9)] == [len(logical), self.gap, self.end, self.capacity]
        memory, info = snapshot(label)
        if self.history:
            self.history.check_memory(memory)
        assert memory[base:base+capacity] == self.expected[base:base+capacity]
        actual = memory[base:base+self.gap]+memory[base+self.end:base+capacity]
        assert actual == logical
        return dict(label=label, bytes=len(logical), sha256=hashlib.sha256(logical).hexdigest(),
                    token=token.hex(), record=record.hex(), base=base, capacity=capacity,
                    gap=self.gap, gap_end=self.end, component=code, snapshot=info, history=history)
