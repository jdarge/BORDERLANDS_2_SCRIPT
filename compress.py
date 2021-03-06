from data import copy_earlier, expand_zeroes
from table import clz_table


def compress(s):
    src = bytearray(s)
    dst = bytearray()

    ip = 0
    length = len(s)
    t = 0

    dst.append(240)
    dst.append((length >> 24) & 0xff)
    dst.append((length >> 16) & 0xff)
    dst.append((length >> 8) & 0xff)
    dst.append(length & 0xff)

    while length > 20 and t + length > 31:
        ll = min(49152, length)
        t = compress_core(src, dst, t, ip, ll)
        ip += ll
        length -= ll
    t += length

    if t > 0:
        ii = len(s) - t

        if len(dst) == 5 and t <= 238:
            dst.append(17 + t)
        elif t <= 3:
            dst[-2] |= t
        elif t <= 18:
            dst.append(t - 3)
        else:
            tt = t - 18
            dst.append(0)
            n, tt = divmod(tt, 255)
            dst.extend("\x00" * n)
            dst.append(tt)
        dst.extend(src[ii: ii + t])

    dst.append(16 | 1)
    dst.append(0)
    dst.append(0)

    return str(dst)


def compress_core(src, dst, ti, ip_start, ip_len):
    dict_entries = [0] * 16384

    in_end = ip_start + ip_len
    ip_end = ip_start + ip_len - 20

    ip = ip_start
    ii = ip_start

    ip += (4 - ti) if ti < 4 else 0
    ip += 1 + ((ip - ii) >> 5)
    while 1:
        while 1:
            if ip >= ip_end:
                return in_end - (ii - ti)
            dv = src[ip: ip + 4]
            dindex = dv[0] | (dv[1] << 8) | (dv[2] << 16) | (dv[3] << 24)
            dindex = ((0x1824429d * dindex) >> 18) & 0x3fff
            m_pos = ip_start + dict_entries[dindex]
            dict_entries[dindex] = (ip - ip_start) & 0xffff
            if dv == src[m_pos: m_pos + 4]:
                break
            ip += 1 + ((ip - ii) >> 5)

        ii -= ti
        ti = 0
        t = ip - ii
        if t != 0:
            if t <= 3:
                dst[-2] |= t
                dst.extend(src[ii: ii + t])
            elif t <= 16:
                dst.append(t - 3)
                dst.extend(src[ii: ii + t])
            else:
                if t <= 18:
                    dst.append(t - 3)
                else:
                    tt = t - 18
                    dst.append(0)
                    n, tt = divmod(tt, 255)
                    dst.extend("\x00" * n)
                    dst.append(tt)
                dst.extend(src[ii: ii + t])
                ii += t

        m_len = 4
        v = read_xor32(src, ip + m_len, m_pos + m_len)
        if v == 0:
            while 1:
                m_len += 4
                v = read_xor32(src, ip + m_len, m_pos + m_len)
                if ip + m_len >= ip_end:
                    break
                elif v != 0:
                    m_len += clz_table[(v & -v) % 37] >> 3
                    break
        else:
            m_len += clz_table[(v & -v) % 37] >> 3

        m_off = ip - m_pos
        ip += m_len
        ii = ip
        if m_len <= 8 and m_off <= 0x0800:
            m_off -= 1
            dst.append(((m_len - 1) << 5) | ((m_off & 7) << 2))
            dst.append(m_off >> 3)
        elif m_off <= 0x4000:
            m_off -= 1
            if m_len <= 33:
                dst.append(32 | (m_len - 2))
            else:
                m_len -= 33
                dst.append(32)
                n, m_len = divmod(m_len, 255)
                dst.extend("\x00" * n)
                dst.append(m_len)
            dst.append((m_off << 2) & 0xff)
            dst.append((m_off >> 6) & 0xff)
        else:
            m_off -= 0x4000
            if m_len <= 9:
                dst.append(0xff & (16 | ((m_off >> 11) & 8) | (m_len - 2)))
            else:
                m_len -= 9
                dst.append(0xff & (16 | ((m_off >> 11) & 8)))
                n, m_len = divmod(m_len, 255)
                dst.extend("\x00" * n)
                dst.append(m_len)
            dst.append((m_off << 2) & 0xff)
            dst.append((m_off >> 6) & 0xff)


def decompress(s):
    dst = bytearray()
    src = bytearray(s)
    ip = 5

    t = src[ip]
    ip += 1
    if t > 17:
        t = t - 17
        dst.extend(src[ip: ip + t])
        ip += t
        t = src[ip]
        ip += 1
    elif t < 16:
        if t == 0:
            t, ip = expand_zeroes(src, ip, 15)
        dst.extend(src[ip: ip + t + 3])
        ip += t + 3
        t = src[ip]
        ip += 1

    while 1:
        while 1:
            if t >= 64:
                copy_earlier(dst, 1 + ((t >> 2) & 7) + (src[ip] << 3), (t >> 5) + 1)
                ip += 1
            elif t >= 32:
                count = t & 31
                if count == 0:
                    count, ip = expand_zeroes(src, ip, 31)
                t = src[ip]
                copy_earlier(dst, 1 + ((t | (src[ip + 1] << 8)) >> 2), count + 2)
                ip += 2
            elif t >= 16:
                offset = (t & 8) << 11
                count = t & 7
                if count == 0:
                    count, ip = expand_zeroes(src, ip, 7)
                t = src[ip]
                offset += (t | (src[ip + 1] << 8)) >> 2
                ip += 2
                if offset == 0:
                    return str(dst)
                copy_earlier(dst, offset + 0x4000, count + 2)
            else:
                copy_earlier(dst, 1 + (t >> 2) + (src[ip] << 2), 2)
                ip += 1

            t = t & 3
            if t == 0:
                break
            dst.extend(src[ip: ip + t])
            ip += t
            t = src[ip]
            ip += 1

        while 1:
            t = src[ip]
            ip += 1
            if t < 16:
                if t == 0:
                    t, ip = expand_zeroes(src, ip, 15)
                dst.extend(src[ip: ip + t + 3])
                ip += t + 3
                t = src[ip]
                ip += 1
            if t < 16:
                copy_earlier(dst, 1 + 0x0800 + (t >> 2) + (src[ip] << 2), 3)
                ip += 1
                t = t & 3
                if t == 0:
                    continue
                dst.extend(src[ip: ip + t])
                ip += t
                t = src[ip]
                ip += 1
            break


def read_xor32(src, p1, p2):
    v1 = src[p1] | (src[p1 + 1] << 8) | (src[p1 + 2] << 16) | (src[p1 + 3] << 24)
    v2 = src[p2] | (src[p2 + 1] << 8) | (src[p2 + 2] << 16) | (src[p2 + 3] << 24)
    return v1 ^ v2
