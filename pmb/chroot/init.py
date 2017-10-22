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
import logging
import os
import glob
import filecmp

import pmb.chroot
import pmb.chroot.apk_static
import pmb.config
import pmb.helpers.repo
import pmb.helpers.run
import pmb.parse.arch


def copy_resolv_conf(args, suffix="native"):
    """
    Use pythons super fast file compare function (due to caching)
    and copy the /etc/resolv.conf to the chroot, in case it is
    different from the host.
    If the file doesn't exist, create an empty file with 'touch'.
    """
    host = "/etc/resolv.conf"
    chroot = args.work + "/chroot_" + suffix + host
    if os.path.exists(host):
        if not os.path.exists(chroot) or not filecmp.cmp(host, chroot):
            pmb.helpers.run.root(args, ["cp", host, chroot])
    else:
        pmb.helpers.run.root(args, ["touch", chroot])


def init(args, suffix="native"):
    # When already initialized: just prepare the chroot
    chroot = args.work + "/chroot_" + suffix
    arch = pmb.parse.arch.from_chroot_suffix(args, suffix)
    emulate = pmb.parse.arch.cpu_emulation_required(args, arch)

    pmb.chroot.mount(args, suffix)
    if os.path.islink(chroot + "/bin/sh"):
        if emulate:
            pmb.chroot.binfmt.register(args, arch)
        copy_resolv_conf(args, suffix)
        pmb.chroot.apk.update_repository_list(args, suffix)
        return

    # Require apk-tools-static
    pmb.chroot.apk_static.init(args)

    # Non-native chroot: require qemu-user-static
    if emulate:
        pmb.chroot.apk.install(args, ["qemu-user-static-repack",
                                      "qemu-user-static-repack-binfmt"])
        pmb.chroot.binfmt.register(args, arch)

    logging.info("(" + suffix + ") install alpine-base")

    # Initialize cache
    apk_cache = args.work + "/cache_apk_" + arch
    pmb.helpers.run.root(args, ["ln", "-s", "/var/cache/apk", chroot +
                                "/etc/apk/cache"])

    # Initialize /etc/apk/keys/, resolv.conf, repositories
    logging.debug(pmb.config.apk_keys_path)
    for key in glob.glob(pmb.config.apk_keys_path + "/*.pub"):
        pmb.helpers.run.root(args, ["cp", key, args.work +
                                    "/config_apk_keys/"])
    copy_resolv_conf(args, suffix)
    pmb.chroot.apk.update_repository_list(args, suffix)

    # Install alpine-base (no clean exit for non-native chroot!)
    pmb.chroot.apk_static.run(args, ["-U", "--root", chroot,
                                     "--cache-dir", apk_cache, "--initdb", "--arch", arch,
                                     "add", "alpine-base"], check=(not emulate))

    # Create device nodes
    for dev in pmb.config.chroot_device_nodes:
        path = chroot + "/dev/" + str(dev[4])
        if not os.path.exists(path):
            pmb.helpers.run.root(args, ["mknod",
                                        "-m", str(dev[0]),  # permissions
                                        path,  # name
                                        str(dev[1]),  # type
                                        str(dev[2]),  # major
                                        str(dev[3]),  # minor
                                        ])
            if not os.path.exists(path):
                raise RuntimeError("Failed to create device node in chroot for " +
                                   dev[4] + "! (This might be caused by setting the work folder" +
                                   " to an eCryptfs folder.)")

    # Non-native chroot: install qemu-user-binary, run apk fix
    if emulate:
        arch_debian = pmb.parse.arch.alpine_to_debian(arch)
        pmb.helpers.run.root(args, ["cp", args.work +
                                    "/chroot_native/usr/bin/qemu-" + arch_debian + "-static",
                                    chroot + "/usr/bin/qemu-" + arch_debian + "-static"])
        pmb.chroot.root(args, ["apk", "fix"], suffix,
                        auto_init=False)

    # Building chroots: create "pmos" user, add symlinks to /home/pmos
    if not suffix.startswith("rootfs_"):
        pmb.chroot.root(args, ["adduser", "-D", "pmos", "-u",
                        pmb.config.chroot_uid_user], suffix, auto_init=False)

        # Create the links (with subfolders if necessary)
        for target, link_name in pmb.config.chroot_home_symlinks.items():
            link_dir = os.path.dirname(link_name)
            if not os.path.exists(chroot + link_dir):
                pmb.chroot.user(args, ["mkdir", "-p", link_dir], suffix)
            pmb.chroot.user(args, ["ln", "-s", target, link_name], suffix)
            pmb.chroot.root(args, ["chown", "pmos:pmos", target],
                            suffix)
