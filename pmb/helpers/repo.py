"""
Copyright 2017 Oliver Smith

This file is part of pmbootstrap.

pmbootstrap is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pmbootstrap is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with pmbootstrap.  If not, see <http://www.gnu.org/licenses/>.
"""
import glob
import os
import hashlib


def files(args):
    """
    Returns all files (apk/buildinfo) with their last modification timestamp
    inside the package repository, sorted by architecture.

    :returns: {"x86_64": {"first.apk": last_modified_timestamp, ... }, ... }
    """
    ret = {}
    for arch_folder in glob.glob(args.work + "/packages/*"):
        arch = os.path.basename(arch_folder)
        ret[arch] = {}
        for file in glob.glob(arch_folder + "/*"):
            basename = os.path.basename(file)
            ret[arch][basename] = os.path.getmtime(file)
    return ret


def diff(args, files_a, files_b=None):
    """
    Returns a list of files, that have been added or modified inside the
    package repository.

    :param files_a: return value from pmb.helpers.repo.files()
    :param files_b: defaults to creating a new list
    :returns: ["x86_64/APKINDEX.tar.gz", "x86_64/package.apk",
               "x86_64/package.buildinfo", ...]
    """
    if not files_b:
        files_b = files(args)

    ret = []
    for arch in files_b.keys():
        for file, timestamp in files_b[arch].items():
            add = False
            if arch not in files_a:
                add = True
            elif file not in files_a[arch]:
                add = True
            elif timestamp != files_a[arch][file]:
                add = True
            if add:
                ret.append(arch + "/" + file)

    return sorted(ret)


def hash(url, length=8):
    """
    Generate the hash, that APK adds to the APKINDEX and apk packages
    in its apk cache folder. It is the "12345678" part in this example:
    "APKINDEX.12345678.tar.gz".

    :param length: The length of the hash in the output file.

    See also: official implementation in apk-tools:
    <https://git.alpinelinux.org/cgit/apk-tools/>

    blob.c: apk_blob_push_hexdump(), "const char *xd"
    apk_defines.h: APK_CACHE_CSUM_BYTES
    database.c: apk_repo_format_cache_index()
    """
    binary = hashlib.sha1(url.encode("utf-8")).digest()
    xd = "0123456789abcdefghijklmnopqrstuvwxyz"
    csum_bytes = int(length / 2)

    ret = ""
    for i in range(csum_bytes):
        ret += xd[(binary[i] >> 4) & 0xf]
        ret += xd[binary[i] & 0xf]

    return ret


def urls(args, user_repository=True, postmarketos_mirror=True):
    """
    Get a list of repository URLs, as they are in /etc/apk/repositories.
    """
    ret = []
    # Local user repository (for packages compiled with pmbootstrap)
    if user_repository:
        ret.append("/mnt/pmbootstrap-packages")

    # Upstream postmarketOS binary repository
    if postmarketos_mirror and args.mirror_postmarketos:
        if os.path.exists(args.mirror_postmarketos):
            ret.append("/mnt/postmarketos-mirror")
        else:
            ret.append(args.mirror_postmarketos)

    # Upstream Alpine Linux repositories
    directories = ["main", "community"]
    if args.alpine_version == "edge":
        directories.append("testing")
    for dir in directories:
        ret.append(args.mirror_alpine + args.alpine_version + "/" + dir)
    return ret


def apkindex_files(args, arch=None):
    """
    Get a list of outside paths to all resolved APKINDEX.tar.gz files for a
    specific arch.
    :param arch: defaults to native
    """
    if not arch:
        arch = args.arch_native

    # Local user repository (for packages compiled with pmbootstrap)
    ret = [args.work + "/packages/" + arch + "/APKINDEX.tar.gz"]

    # Upstream postmarketOS binary repository
    urls_todo = []
    mirror = args.mirror_postmarketos
    if mirror:
        if os.path.exists(mirror):
            ret.append(mirror + "/" + arch + "/APKINDEX.tar.gz")
        else:
            # Non-local path: treat it like other URLs
            urls_todo.append(mirror)

    # Resolve the APKINDEX.$HASH.tar.gz files
    urls_todo += urls(args, False, False)
    for url in urls_todo:
        ret.append(args.work + "/cache_apk_" + arch + "/APKINDEX." +
                   hash(url) + ".tar.gz")

    return ret
