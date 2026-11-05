#!/usr/bin/env python3
"""Minimal Android boot image packer (header v1/v2), pure stdlib.

Written because there is no mkbootimg on this machine.  Field order and
layout follow system/tools/mkbootimg/bootimg.h.
"""
import argparse
import gzip
import hashlib
import io
import os
import struct

PAGE = 4096
MAGIC = b"ANDROID!"


def _pad(buf, page=PAGE):
    rem = len(buf) % page
    return buf if rem == 0 else buf + b"\0" * (page - rem)


def minimal_ramdisk():
    """A valid, empty newc cpio (just the trailer), gzipped.

    ABL rejects a zero-length ramdisk on some builds, so hand it a real one.
    """
    name = b"TRAILER!!!\0"
    hdr = b"070701"
    # newc header: magic + 13 eight-digit hex fields
    # ino mode uid gid nlink mtime filesize devmajor devminor rdevmajor
    # rdevminor namesize check
    body = b"".join(b"%08x" % f for f in
                    [0, 0o040755, 0, 0, 1, 0, 0, 0, 0, 0, 0, len(name), 0])
    raw = hdr + body + name
    raw += b"\0" * ((4 - len(raw) % 4) % 4)
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(raw)
    return buf.getvalue()


def build(kernel, ramdisk, header_version=1, dtb=None, dtbo=None,
          kernel_addr=0x8000, ramdisk_addr=0x01000000,
          second_addr=0x00f00000, tags_addr=0x00000100,
          dtb_addr=0x01f00000, cmdline="", name="", os_version=0,
          os_patch_level=0, page=PAGE, osv_raw=None):
    if header_version == 2 and dtb is None:
        raise ValueError("header v2 needs a dtb")
    hdr_sz = 1648 if header_version < 2 else 1660

    cmd = cmdline.encode()[:511]
    nm = name.encode()[:15]
    osv = osv_raw if osv_raw is not None else \
        (((os_version << 11) | os_patch_level) & 0xffffffff)
    ident = hashlib.sha1()
    for blob, sz in ((kernel, len(kernel)), (ramdisk, len(ramdisk))):
        ident.update(blob)
        ident.update(struct.pack("<I", sz))
    if dtb:
        ident.update(dtb)
        ident.update(struct.pack("<I", len(dtb)))

    h = struct.pack(
        "<8s10I16s512s32s1024s",
        MAGIC,
        len(kernel), kernel_addr,
        len(ramdisk), ramdisk_addr,
        0, second_addr,
        tags_addr, page, header_version, osv,
        nm, cmd, ident.digest(), b"",
    )
    if header_version >= 1:
        h += struct.pack("<IQI", len(dtbo) if dtbo else 0,
                         0, hdr_sz)
    if header_version >= 2:
        h += struct.pack("<IQ", len(dtb) if dtb else 0, dtb_addr)
    assert len(h) == hdr_sz, (len(h), hdr_sz)

    out = _pad(h, page) + _pad(kernel, page) + _pad(ramdisk, page)
    if dtbo:
        out += _pad(dtbo, page)
    if dtb:
        out += _pad(dtb, page)
    return out


def unpack(data):
    """Split a boot image into its parts (v0-v2)."""
    magic, ksz, ka, rsz, ra, ssz, sa, tags, page, hv, osv = \
        struct.unpack_from("<8s10I", data, 0)
    if magic != MAGIC:
        raise ValueError("不是 boot.img")
    cmdline = data[64:576].split(b"\0")[0].decode("latin1")
    dtbo_sz = hdr_sz = dtb_sz = 0
    dtb_addr = 0
    if hv >= 1:
        dtbo_sz, = struct.unpack_from("<I", data, 1632)
        hdr_sz, = struct.unpack_from("<I", data, 1644)
    if hv >= 2:
        dtb_sz, = struct.unpack_from("<I", data, 1648)
        dtb_addr, = struct.unpack_from("<Q", data, 1652)

    def al(x):
        return (x + page - 1) // page * page

    off = page
    kernel = data[off:off + ksz]
    off += al(ksz)
    ramdisk = data[off:off + rsz]
    off += al(rsz)
    second = data[off:off + ssz]
    off += al(ssz)
    dtbo = data[off:off + dtbo_sz] if dtbo_sz else b""
    off += al(dtbo_sz) if dtbo_sz else 0
    dtb = data[off:off + dtb_sz] if dtb_sz else b""
    return dict(kernel=kernel, ramdisk=ramdisk, second=second, dtbo=dtbo,
                dtb=dtb, header_version=hv, kernel_addr=ka, ramdisk_addr=ra,
                second_addr=sa, tags_addr=tags, dtb_addr=dtb_addr,
                page=page, cmdline=cmdline, osv_raw=osv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel", required=True)
    ap.add_argument("--ramdisk")
    ap.add_argument("--dtb")
    ap.add_argument("--header-version", type=int, default=1)
    ap.add_argument("--cmdline", default="")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()

    kernel = open(a.kernel, "rb").read()
    ramdisk = open(a.ramdisk, "rb").read() if a.ramdisk else minimal_ramdisk()
    dtb = open(a.dtb, "rb").read() if a.dtb else None

    img = build(kernel, ramdisk, header_version=a.header_version,
                dtb=dtb, cmdline=a.cmdline)
    with open(a.out, "wb") as f:
        f.write(img)
    print("kernel   %d B" % len(kernel))
    print("ramdisk  %d B" % len(ramdisk))
    print("dtb      %s" % (("%d B" % len(dtb)) if dtb else "-"))
    print("written  %s (%d B, %.2f MiB)" % (a.out, len(img), len(img) / 1048576))


if __name__ == "__main__":
    main()
