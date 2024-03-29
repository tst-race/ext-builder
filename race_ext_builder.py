#
# Copyright 2023 Two Six Technologies
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import logging
import os
import subprocess
import sys
from typing import Any, List, Mapping, Optional, Tuple, Union


logger = logging.root


# Constants
TARGET_LINUX_x86_64 = "linux-x86_64"
TARGET_LINUX_arm64_v8a = "linux-arm64-v8a"
TARGET_ANDROID_x86_64 = "android-x86_64"
TARGET_ANDROID_arm64_v8a = "android-arm64-v8a"


def get_arg_parser(
        name: str,
        version: str,
        revision: int,
        caller: str,
        targets: Optional[List[str]] = None,
    ) -> argparse.ArgumentParser:
    """Get command-line arguments parser pre-configured for common arguments"""
    parser = argparse.ArgumentParser(
        description=f"Build {name}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Args that shouldn't really need to ever be set by the user, but we
    # allow for them to be overridden, and mainly use them as a means of
    # passing them around
    parser.add_argument(
        "--name",
        default=name,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--code-dir",
        default=os.path.dirname(os.path.abspath(caller)),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--source-dir",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--build-dir",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--install-dir",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--install-prefix",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--log-file",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--pkg-file",
        help=argparse.SUPPRESS,
    )
    # Real user-level args
    parser.add_argument(
        "--version",
        default=version,
        help=f"Version of {name}",
        type=str,
    )
    parser.add_argument(
        "--revision",
        default=revision,
        help="Build revision",
        type=int,
    )
    parser.add_argument(
        "--target",
        choices=targets or [TARGET_LINUX_x86_64, TARGET_LINUX_arm64_v8a, TARGET_ANDROID_x86_64, TARGET_ANDROID_arm64_v8a],
        help="Target to build",
        required=True,
    )
    parser.add_argument(
        "--num-threads",
        default=os.cpu_count(),
        help="Number of concurrent jobs to run (set to # CPUs for optimal use)",
        type=int,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands but do not execute",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    return parser


def normalize_args(args: argparse.Namespace) -> argparse.Namespace:
    """Ensure all required args are set, using user-provided values to derive defaults"""
    cache_dir = f"/build/cache/{args.name}/{args.version}-{args.revision}/{args.target}"
    if not args.source_dir:
        args.source_dir = f"{cache_dir}/source"
    if not args.build_dir:
        args.build_dir = f"{cache_dir}/build"
    if not args.install_dir:
        args.install_dir = f"{cache_dir}/install"
    if not args.install_prefix:
        if args.target.startswith("linux"):
            args.install_prefix = "/usr/local"
        elif args.target == TARGET_ANDROID_x86_64:
            args.install_prefix = "/android/x86_64"
        elif args.target == TARGET_ANDROID_arm64_v8a:
            args.install_prefix = "/android/arm64-v8a"
    if not args.log_file:
        args.log_file = f"/build/cache/{args.name}-{args.version}-{args.revision}-{args.target}.log"
    if not args.pkg_file:
        args.pkg_file = f"/build/cache/{args.name}-{args.version}-{args.revision}-{args.target}.tar.gz"
    return args


def make_dirs(args: argparse.Namespace):
    """Create all cache directories"""
    os.makedirs(args.source_dir, exist_ok=True)
    os.makedirs(args.build_dir, exist_ok=True)
    os.makedirs(args.install_dir, exist_ok=True)
    os.makedirs(args.install_prefix, exist_ok=True)


class ConsoleFormatter(logging.Formatter):

    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    format = "%(asctime)s (%(levelname)s): %(message)s"

    default_formatter = logging.Formatter(grey + format + reset)
    formatters = {
        logging.DEBUG: logging.Formatter(grey + format + reset),
        logging.INFO: logging.Formatter(green + format + reset),
        logging.WARNING: logging.Formatter(yellow + format + reset),
        logging.ERROR: logging.Formatter(red + format + reset),
        logging.CRITICAL: logging.Formatter(bold_red + format + reset),
    }

    def format(self, record):
        formatter = self.formatters.get(record.levelno, self.default_formatter)
        return formatter.format(record)


def setup_logger(args: argparse.Namespace):
    """Set up python logger"""
    logging.basicConfig(
        filemode='w',
        filename=args.log_file,
        force=True,
        format="%(asctime)s %(levelname)-8s : %(message)s",
        level=logging.DEBUG,
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ConsoleFormatter())
    console_handler.setLevel(logging.DEBUG if args.dry_run or args.verbose else logging.INFO)
    logging.root.addHandler(console_handler)


def install_packages(args: argparse.Namespace, packages: List[Union[str, Tuple[str, str, Optional[bool]]]]):
    """
    Install packages via apt

    Package list is a list of either strings, or tuple of package name, version,
    and whether the package is target-architecture dependent. For example:
    ```
    install_packages(args, [
        "versionlesspkg",
        "versionpinnedpkg=a.b.c",
        ("versionlesspkg"),
        ("versionlesspkg", "a.b.c"),
        ("archspecificpkg", None, True),
        ("archspecificversionpinnedpkg", "a.b.c", True),
    ])
    ```
    """
    arch = ":arm64" if "arm" in args.target else ":amd64"
    pkgs = []
    for package in packages:
        if type(package) is str:
            pkgs.append(package)
        elif type(package) is tuple:
            pkg_name = package[0]
            pkg_ver = f"={package[1]}" if len(package) > 1 and package[1] is not None else ""
            pkg_arch = arch if len(package) > 2 and package[2] else ""
            pkgs.append(f"{pkg_name}{pkg_arch}{pkg_ver}")

    logger.info(f"Installing {', '.join(pkgs)} from apt")
    execute(args, ["apt-get", "update", "-y"])
    execute(args, ["apt-get", "install", "-y"] + pkgs)


def install_ext(args: argparse.Namespace, packages: List[Tuple[str, str]]):
    """Install external dependencies"""
    logger.info("Installing external dependencies from github")
    for (name, version) in packages:
        logger.info(f"Installing {name}-{version}")
        local_filepath = f"/build/cache/{name}-{version}-{args.target}.tar.gz"
        if not os.path.exists(local_filepath):
            remote_url = f"https://github.com/tst-race/ext-{name}/releases/download/{version}/{name}-{version}-{args.target}.tar.gz"
            logger.info(f"Fetching {remote_url} to {local_filepath}")
            execute(args, [
                "wget",
                f"--output-document={local_filepath}",
                remote_url,
            ])
        else:
            logger.debug(f"Using cached {local_filepath}")

        execute(args, [
            "tar",
            "--extract",
            f"--file={local_filepath}",
            f"--directory={args.install_prefix}",
        ])


def fetch_source(args: argparse.Namespace, source: Optional[str], extract: Optional[str]):
    """Fetch (and optionally extract) source archive"""
    base_filename = os.path.basename(source)
    local_filepath = os.path.join(args.source_dir, base_filename)
    if not os.path.exists(local_filepath):
        logger.info(f"Fetching {source} to {local_filepath}")
        execute(args, [
            "wget",
            f"--output-document={local_filepath}",
            "--no-verbose",
            source,
        ])
    else:
        logger.debug(f"Using cached {local_filepath}")

    if extract == "tar.gz":
        logger.info(f"Extracting {source}")
        execute(args, [
            "tar",
            "--extract",
            f"--file={local_filepath}",
            f"--directory={args.source_dir}",
        ])


def create_standard_envvars(args: argparse.Namespace) -> Mapping[str, str]:
    """Create standard environment variables for compilers based on target"""
    env = {
        "DESTDIR": args.install_dir,
    }
    if args.target == TARGET_LINUX_x86_64:
        env.update({
            "CC": "clang -target x86_64-linux-gnu",
            "CXX": "clang++ -target x86_64-linux-gnu",
        })
    elif args.target == TARGET_LINUX_arm64_v8a:
        env.update({
            "CC": "clang -target aarch64-linux-gnu",
            "CXX": "clang++ -target aarch64-linux-gnu",
        })
    elif args.target == TARGET_ANDROID_x86_64:
        env.update({
            "AR": "llvm-ar",
            "AS": "x86_64-linux-android-as",
            "CC": "x86_64-linux-android29-clang",
            "CXX": "x86_64-linux-android29-clang++",
            "LD": "llvm-ld",
            "RANLIB": "llvm-ranlib",
            "READELF": "llvm-readelf",
            "STRIP": "llvm-strip",
        })
    elif args.target == TARGET_ANDROID_arm64_v8a:
        env.update({
            "AR": "llvm-ar",
            "AS": "aarch64-linux-android-as",
            "CC": "aarch64-linux-android29-clang",
            "CXX": "aarch64-linux-android29-clang++",
            "LD": "llvm-ld",
            "RANLIB": "llvm-ranlib",
            "READELF": "llvm-readelf",
            "STRIP": "llvm-strip",
        })
    if args.target.startswith("android"):
        toolchain_dir = f"{os.environ['ANDROID_NDK']}/toolchains/llvm/prebuilt/linux-x86_64/bin"
        if os.path.exists(toolchain_dir):
            env["PATH"] = f"{toolchain_dir}:{os.environ['PATH']}"
    logger.debug(f"Using standard env vars: {env}")
    return env


def execute(args: argparse.Namespace, cmd: List[str], cwd: Optional[str] = None, env: Optional[Mapping[str, Any]] = None):
    """Execute command"""
    # Normalize command array
    cmd = [str(c) for c in cmd]
    # If env vars were provided, add them to execution environment
    cmd_env = None
    if env:
        cmd_env = {k: v for (k,v) in os.environ.items()}
        cmd_env.update(env)

    logger.debug(f"Executing: {' '.join(cmd)}")
    if not args.dry_run:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=cmd_env, shell=False, universal_newlines=True)
        for line in proc.stdout:
            logger.debug(line.rstrip())
        proc.wait()
        if proc.returncode != 0:
            raise Exception(f"Command {cmd} returned with non-zero exit status {proc.returncode}")


def copy(args: argparse.Namespace, src: str, dest: str):
    """Copy a file or directory to the given destination"""
    logger.info(f"Copying {src} to {dest}")
    cmd = ["cp"]
    if os.path.isdir(src):
        cmd.extend(["--recursive", "--preserve"])
    cmd.extend([src, dest])
    execute(args, cmd)


def find_and_replace(args: argparse.Namespace, root_dir: str, file_pattern: str, regex: str, replacement: str):
    """Perform a find and replace"""
    execute(args, [
        "bash",
        "-c",
        f"find {root_dir} -type f -name '{file_pattern}' -print0 | xargs -0 sed -i \"s/{regex}/{replacement}/g\"",
    ])


def create_package(args: argparse.Namespace, subdir: Optional[str] = ""):
    """Create tarball package"""
    logger.info(f"Packaging {args.install_dir} into {args.pkg_file}")
    execute(args, [
        "tar",
        "--create",
        f"--file={args.pkg_file}",
        "--gzip",
        f"--directory={args.install_dir}{subdir}",
        ".",
    ])
