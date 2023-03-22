#!/usr/bin/env python3

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

"""
RACE external project builder script
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import timedelta


default_cache_dir = os.environ.get(
    "EXT_CACHE_DIR",
    f"{os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}/ext-cache"
)
build_lib_file = f"{os.path.dirname(os.path.abspath(__file__))}/race_ext_builder.py"


def get_host_target() -> str:
    """Get target corresponding to the current host"""
    return "linux-x86_64" if "x86" in os.uname().machine else "linux-arm64-v8a"


def get_host_platform() -> str:
    """Get Docker platform corresponding to the current host"""
    return "linux/amd64" if "x86" in os.uname().machine else "linux/arm64"


def get_cli_arguments():
    """Parse command-line arguments to the script"""
    parser = argparse.ArgumentParser(
        description="Build external project",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "project",
        help="Path to external project to build",
    )
    parser.add_argument(
        "project_args",
        help="Pass-through args for the project build script",
        nargs="*",
    )
    parser.add_argument(
        "--target",
        choices=["linux-x86_64", "linux-arm64-v8a", "android-x86_64", "android-arm64-v8a"],
        default=get_host_target(),
        help="Target to build",
    )
    parser.add_argument(
        "--image",
        default="ext-builder", # TODO use ghcr.io image
        help="Docker image to use for building the external project",
        type=str,
    )
    parser.add_argument(
        "--platform",
        default=get_host_platform(),
        help="Platform to use for docker image",
        type=str,
    )
    parser.add_argument(
        "--cache-dir",
        default=default_cache_dir,
        help="Location of cache dir",
        type=str,
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
    return parser.parse_intermixed_args()


def run_build(
    project_dir: str,
    args: argparse.Namespace,
):
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{project_dir}:/build/code",
        "-v",
        f"{args.cache_dir}:/build/cache",
        "-v",
        f"{build_lib_file}:/usr/lib/python3.8/race_ext_builder.py",
        "--platform",
        args.platform,
    ]
    cmd.extend([
        args.image,
        "python3",
        "-u",
        "/build/code/build.py",
        "--target",
        args.target,
    ])
    if args.project_args:
        cmd.extend(args.project_args)

    if args.dry_run or args.verbose:
        print(f"Executing: {' '.join(cmd)}")
        print()
    if not args.dry_run:
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    args = get_cli_arguments()

    project_dir = os.path.abspath(args.project)
    if not os.path.exists(f"{project_dir}/build.py"):
        print(f"build.py does not exist in {project_dir}")
        sys.exit(1)

    start_time = time.time()
    try:
        run_build(project_dir, args)
    finally:
        stop_time = time.time()
        duration = timedelta(seconds=stop_time - start_time)
        print(f"Took {duration} to execute")
