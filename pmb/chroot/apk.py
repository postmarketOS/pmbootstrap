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
import pmb.chroot
import pmb.config
import pmb.parse.apkindex
import pmb.parse.other


def check_min_version(args, suffix="native"):
    """
    Check the minimum apk version, before running it the first time in the
    current session (lifetime of one pmbootstrap call).
    """
    # Skip if we already did this
    if suffix in args.cache["apk_min_version_checked"]:
        return

    # Read the version from apk and from the config
    pkgver = pmb.chroot.root(args, ["apk", "--version"], suffix,
                             return_stdout=True)
    pkgver = pkgver.split(" ")[1].split(",")[0]
    pkgver_min = pmb.config.apk_tools_static_min_version.split("-")[0]

    # Compare
    if pmb.parse.apkindex.compare_version(pkgver, pkgver_min) == -1:
        raise RuntimeError("You have an outdated version of the 'apk' package"
                           " manager installed (your version: " + pkgver +
                           ", expected at least: " + pkgver_min + "). Delete"
                           " your http cache and zap all chroots, then try again:"
                           " 'pmbootstrap zap -hc'")
    args.cache["apk_min_version_checked"].append(suffix)


def install(args, packages, suffix="native", build=True):
    """
    :param build: automatically build the package, when it does not exist yet
        and it is inside the pm-aports folder. Checking this is expensive - if
        you know, that all packages are provides by upstream repos, set this to
        False!
    """
    # Initialize chroot
    check_min_version(args, suffix)
    pmb.chroot.init(args, suffix)

    # Filter already installed packages
    packages_installed = installed(args, suffix)
    packages_todo = []
    for package in packages:
        if package not in packages_installed:
            packages_todo.append(package)
    if not len(packages_todo):
        return

    # Build packages if necessary
    arch = pmb.parse.arch.from_chroot_suffix(args, suffix)
    if build:
        for package in packages_todo:
            pmb.build.package(args, package, arch)

    # Sanitize packages: don't allow '--allow-untrusted' and other options
    # to be passed to apk!
    for package in packages_todo:
        if package.startswith("-"):
            raise ValueError("Invalid package name: " + package)

    # Install everything
    logging.info("(" + suffix + ") install " + " ".join(packages_todo))
    pmb.chroot.root(args, ["apk", "--no-progress", "add"] + packages_todo,
                    suffix)


def upgrade(args, suffix="native", update_index=True):
    """
    Upgrade all packages installed in a chroot
    """
    check_min_version(args, suffix)
    pmb.chroot.init(args, suffix)
    if update_index:
        pmb.chroot.root(args, ["apk", "update"], suffix)

    # -a: also update previously downgraded (and therefore pinned) packages
    pmb.chroot.root(args, ["apk", "upgrade", "-a"], suffix)


def installed(args, suffix="native"):
    """
    Get all installed packages and their versions.
    :returns: { "hello-world": {"package": "hello-world-1-r2", "pkgrel": "2",
        "pkgver": "1", "pkgname": "hello-world"}, ...}
    """
    check_min_version(args, suffix)
    list = pmb.chroot.user(args, ["apk", "info", "-vv"], suffix,
                           return_stdout=True)
    # Parse the output into a dictionary
    ret = {}
    for line in list.split("\n"):
        if not line.rstrip():
            continue
        package = line.split(" - ")[0]
        split = pmb.parse.other.package_split(package)
        ret[split["pkgname"]] = split
    return ret
