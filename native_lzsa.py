"""LZSA2 raw-block packing and a bounded Python decoder.

Independent implementation written from the LZSA2 block format description.
The LZSA2 format itself is Emmanuel Marty's (the LZSA project); no code from
that project is used here. SPDX-License-Identifier: GPL-3.0-or-later

pack() is a deterministic optimal-cost parser: a forward shortest-path search
over byte positions whose edges are literals, explicit-offset matches and
repeat-offset matches, each costed in bits exactly as the block format encodes
them (nibble fields cost 4 bits). Every position keeps several arrivals that
differ in their repeat offset, so later repeat matches can be found. Matches
come from exact two-byte hash chains: every length is tried at its nearest
(cheapest-to-encode) distance, and farther distances at their full length.
"""

ARRIVALS = 64       # arrivals kept per position, one per distinct repeat offset
CHAIN = 256         # hash-chain candidates examined per position
ALL_LENGTHS = 64    # every length up to this is tried; longer: only key lengths
NICE = 512          # a match this long is taken outright (skips its interior)
MAX_BLOCK = 65535


def _literal_extra(count):
    return 0 if count < 3 else 4 if count < 18 else 12 if count < 256 else 28


def _match_extra(count):
    return 0 if count < 9 else 4 if count < 24 else 12 if count < 256 else 28


def _offset_cost(distance):
    return 4 if distance <= 32 else 8 if distance <= 512 else 12 if distance <= 8704 else 16


# Marginal bit cost of the (n+1)th literal of a run, and the token plus length
# extension bits of a match of n bytes.
_LITERAL = [8 + _literal_extra(n + 1) - _literal_extra(n) for n in range(MAX_BLOCK + 1)]
_MATCH = [8 + _match_extra(n) for n in range(MAX_BLOCK + 1)]
_OFFSET = [0] + [_offset_cost(d) for d in range(1, MAX_BLOCK + 1)]


def _lengths(low, high):
    """Match lengths worth trying in low..high (inclusive)."""
    if high <= ALL_LENGTHS:
        return range(low, high + 1)
    keep = list(range(low, ALL_LENGTHS + 1))
    keep += [n for n in (8, 23, 255) if ALL_LENGTHS < n < high and n >= low]
    keep.append(high)
    return keep


def _parse(data):
    """Return the cheapest command list as (literal count, match length, distance)."""
    size = len(data)
    chain = [-1] * size
    head = {}
    for at in range(size - 1):
        key = data[at] | data[at + 1] << 8
        chain[at] = head.get(key, -1)
        head[key] = at

    def extend(source, at, count, limit):
        step = 8
        while count < limit:
            span = limit - count if limit - count < step else step
            if data[source+count:source+count+span] == data[at+count:at+count+span]:
                count += span
                step <<= 1
            elif span <= 8:
                while data[source+count] == data[at+count]:
                    count += 1
                return count
            else:
                step = span >> 1
        return limit

    # A node is (cost, repeat distance, literal run, parent, match length, distance).
    arrivals = [None] * (size + 1)
    arrivals[0] = {0: (0, 0, 0, None, 0, 0)}

    def arrive(at, node):
        slot = arrivals[at]
        if slot is None:
            arrivals[at] = {node[1]: node}
            return
        repeat = node[1]
        old = slot.get(repeat)
        if old is not None:
            if node[0] < old[0]:
                slot[repeat] = node
            return
        if len(slot) < ARRIVALS:
            slot[repeat] = node
            return
        worst = max(slot, key=lambda r: slot[r][0])
        if node[0] < slot[worst][0]:
            del slot[worst]
            slot[repeat] = node

    literal, match, offset = _LITERAL, _MATCH, _OFFSET
    skip = 0
    for at in range(size):
        slot = arrivals[at]
        if at < skip or slot is None:
            continue
        nodes = list(slot.values())
        best = min(nodes, key=lambda node: node[0])
        for node in nodes:
            arrive(at + 1, (node[0] + literal[node[2]], node[1], node[2] + 1, node, 0, 0))
        limit = size - at
        if limit < 2:
            continue
        # Repeat-offset matches: no offset bits, and each keeps its own state.
        for node in nodes:
            distance = node[1]
            if distance and distance <= at and data[at-distance] == data[at] \
                    and data[at-distance+1] == data[at+1]:
                longest = extend(at - distance, at, 2, limit)
                for length in _lengths(2, longest):
                    arrive(at + length, (node[0] + match[length], distance, 0, node, length, distance))
        # Explicit-offset matches leave the same state whatever preceded them,
        # so only the cheapest arrival here needs to extend them. Each length
        # gets its nearest (cheapest) distance; a farther distance that adds
        # no length is still kept at its full length, because as the next
        # repeat offset it can make a later match free of offset bits.
        longest, depth, source = 1, CHAIN, chain[at]
        base = best[0]
        while source >= 0 and depth:
            length = extend(source, at, 2, limit)
            distance = at - source
            cost = base + offset[distance]
            if length > longest:
                for count in _lengths(longest + 1, length):
                    arrive(at + count, (cost + match[count], distance, 0, best, count, distance))
                longest = length
                if length >= limit:
                    break
            else:
                arrive(at + length, (cost + match[length], distance, 0, best, length, distance))
            source = chain[source]
            depth -= 1
        if longest >= NICE:
            skip = at + longest

    final = min(arrivals[size].values(), key=lambda node: node[0])
    steps = []
    node = final
    while node[3] is not None:
        steps.append((node[4], node[5]))
        node = node[3]
    steps.reverse()
    commands, run = [], 0
    for length, distance in steps:
        if length:
            commands.append((run, length, distance))
            run = 0
        else:
            run += 1
    commands.append((run, 0, 0))
    return commands


def _encode(data, commands):
    out = bytearray()
    half = None           # index of a byte whose low nibble is still free

    def nibble(value):
        nonlocal half
        if half is None:
            half = len(out)
            out.append(value << 4)
        else:
            out[half] |= value
            half = None

    def extension(total, bias, field, word):
        # total is the real count; the token holds total-bias up to `field`.
        # Beyond it a nibble follows, nibble 15 escapes to a byte, and the
        # byte value `word` escapes to the real count as a 16-bit LE word.
        stored = total - bias
        if stored < field:
            return
        if stored - field < 15:
            nibble(stored - field)
            return
        nibble(15)
        if total < 256:
            out.append(stored - field - 15)
        else:
            out.append(word)
            out.extend(total.to_bytes(2, 'little'))

    at, previous = 0, None
    for literals, length, distance in commands:
        end = length == 0
        if end:
            # The end command's offset is never used. The format text shows a
            # 9-bit offset; the repeat form has no offset field and saves a byte.
            kind, fields = 7, []
        elif distance == previous:
            kind, fields = 7, []
        else:
            value = -distance & 0xffff
            if distance <= 32:
                kind, fields = (~value & 1), [('nibble', value >> 1 & 15)]
            elif distance <= 512:
                kind, fields = 2 | (~value >> 8 & 1), [('byte', value & 255)]
            elif distance <= 8704:
                value = (value + 512) & 0xffff
                kind, fields = 4 | (~value >> 8 & 1), [('nibble', value >> 9 & 15), ('byte', value & 255)]
            else:
                kind, fields = 6, [('byte', value >> 8), ('byte', value & 255)]
            previous = distance
        out.append(kind << 5 | min(literals, 3) << 3 | (7 if end else min(length - 2, 7)))
        extension(literals, 0, 3, 239)
        out += data[at:at+literals]
        at += literals
        for field, value in fields:
            if field == 'nibble':
                nibble(value)
            else:
                out.append(value)
        if end:
            nibble(15)
            out.append(232)
        else:
            extension(length, 2, 7, 233)
            at += length
    return bytes(out)


def pack(data):
    data = bytes(data)
    if not 1 <= len(data) <= MAX_BLOCK:
        raise ValueError('a raw boot block must contain 1..65535 bytes')
    result = _encode(data, _parse(data))
    if unpack(result, len(data)) != data:
        raise ValueError('LZSA2 round trip differs from the input')
    return result


def unpack(data, length):
    """Decode one raw forward block; never read or copy beyond its bounds."""
    if not 0 <= length <= 65535:
        raise ValueError('invalid decoded length')
    at, pending, previous = 0, None, None
    out = bytearray()

    def byte():
        nonlocal at
        if at >= len(data):
            raise ValueError('truncated LZSA2 input')
        value = data[at]
        at += 1
        return value

    def nibble():
        nonlocal pending
        if pending is not None:
            value, pending = pending, None
            return value
        value = byte()
        pending = value & 15
        return value >> 4

    def count(value, short, base, end=False):
        if value < short:
            return value + base
        value += nibble() + base
        if value < short + 15 + base:
            return value
        extra = byte()
        value += extra
        if value < 256:
            return value
        if end and value == 256:
            return None
        if value != 257:
            raise ValueError('invalid LZSA2 extended length')
        value = byte() | byte() << 8
        if value == 0:
            raise ValueError('zero LZSA2 extended length')
        return value

    while True:
        token = byte()
        literals = count((token >> 3) & 3, 3, 0)
        if at + literals > len(data) or len(out) + literals > length:
            raise ValueError('LZSA2 literals exceed input or output')
        out += data[at:at+literals]
        at += literals
        kind = token >> 5
        z = (~kind) & 1
        if kind < 2:
            offset = (0xffe0 | nibble() << 1 | z) - 65536
        elif kind < 4:
            offset = (0xfe00 | z << 8 | byte()) - 65536
        elif kind < 6:
            high = nibble()
            offset = (0xe000 | high << 9 | z << 8 | byte()) - 65536 - 512
        elif kind == 6:
            offset = (byte() << 8 | byte()) - 65536
        else:
            offset = previous
        matches = count(token & 7, 7, 2, end=True)
        if matches is None:
            if at != len(data) or len(out) != length:
                raise ValueError('wrong LZSA2 input or output length')
            return bytes(out)
        if offset is None or not -len(out) <= offset < 0 or len(out)+matches > length:
            raise ValueError('LZSA2 match exceeds decoded output')
        previous = offset
        for _ in range(matches):
            out.append(out[len(out)+offset])
