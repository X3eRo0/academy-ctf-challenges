#!/usr/bin/env python3
"""
CTF Challenge Packaging & Deployment Script
Usage: python main.py [OPTIONS] [SERVICE...]

This script:
  1) Builds checker and vulnbox tar.gz for all services that contain a `.service` file.
     - Uses each service's `config.json` to decide which files to include.
     - Outputs to:
         packages/vulnbox/<service_name>_vb.tar.gz
         packages/checker/<service_name>_ch.tar.gz
  2) With --server-install, uploads all built tarballs to x3ero0.dev and installs each checker:
     - Creates /opt/checker/<service>
     - Extracts the checker tarball into /opt/checker/<service>
     - Copies <service>.env to /etc/ctf-gameserver/<service>.env
     - chown -R ctf-checkerrunner:ctf-checkerrunner /opt/checker
     - If /opt/env doesn't exist, creates venv and links ctf_gameserver, then installs requirements

Options:
  --server-install    Upload packages and install checkers on remote gameserver via SSH
  --help, -h          Show this help message
"""

import os
import sys
import argparse
import json
import shlex
import subprocess
import shutil
import glob
import tarfile
from pathlib import Path
from typing import List, Optional, Tuple

# Configuration
CHECKER_BASE_DIR = "/opt/checker"
CHECKER_CONFIG_DIR = "/etc/ctf-gameserver"
CHECKER_USER = "ctf-checkerrunner"
PACKAGE_DIR = "./packages"
PACKAGE_CHECKER_DIR = os.path.join(PACKAGE_DIR, "checker")
PACKAGE_VULNBOX_DIR = os.path.join(PACKAGE_DIR, "vulnbox")
SSH_HOST = "root@x3ero0.dev"


# Colors for output
class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    NC = "\033[0m"  # No Color


def log_info(message: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}[+]{Colors.NC} {message}")


def log_success(message: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}[*]{Colors.NC} {message}")


def log_warning(message: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}[!]{Colors.NC} {message}")


def log_error(message: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}[X]{Colors.NC} {message}")


def check_root() -> None:
    """Check if running as root for local installation operations."""
    if os.geteuid() != 0:
        log_error("This script must be run as root for local checker installation")
        log_info(
            "Use 'sudo python3 deploy_challenges.py' or run with --package or --server-install option only"
        )
        sys.exit(1)


def check_user_exists(user: str) -> None:
    """Check if user exists (for local installation)."""
    try:
        subprocess.run(["id", user], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        log_error(f"User '{user}' does not exist")
        log_info(f"Please create the user first: sudo useradd -r -s /bin/false {user}")
        sys.exit(1)


def check_ssh_connectivity() -> None:
    """Check SSH connectivity to gameserver."""
    log_info(f"Testing SSH connectivity to {SSH_HOST}...")

    try:
        result = subprocess.run(
            [
                "ssh",
                "-o",
                "ConnectTimeout=10",
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                SSH_HOST,
                "echo 'SSH connection successful'",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        log_success("SSH connectivity verified")
    except subprocess.CalledProcessError as e:
        log_error(f"Cannot connect to {SSH_HOST} via SSH (exit code: {e.returncode})")
        log_error(f"SSH output: {e.stderr}")
        log_info("Please ensure:")
        log_info("  1. SSH key authentication is set up")
        log_info("  2. Host is reachable")
        log_info("  3. You have root access on the server")
        log_info("  4. Your SSH config is properly set up")
        log_info(f"Manual test command: ssh {SSH_HOST} 'echo test'")
        sys.exit(1)


def get_services_with_service_file() -> List[str]:
    """Return service directories that contain a `.service` file."""
    candidates = []
    for item in Path(".").iterdir():
        if item.is_dir() and item.name not in [".git", "packages"]:
            if (item / ".service").exists():
                candidates.append(item.name)
    return sorted(candidates)


def find_env_file(service_dir: Path) -> Optional[Path]:
    """Prefer `<service>.env`; otherwise, return the first `*.env` file."""
    preferred = service_dir / f"{service_dir.name}.env"
    if preferred.exists():
        return preferred
    env_files = list(service_dir.glob("*.env"))
    if not env_files:
        return None
    if len(env_files) > 1:
        log_warning(f"Service '{service_dir.name}' has multiple .env files:")
        for env_file in env_files:
            print(f"  {env_file}")
        log_info("Will use the first one found")
    return env_files[0]


def validate_service_for_packaging(service: str) -> bool:
    """Validate that a service can be packaged (requires .service)."""
    service_path = Path(service)
    if not service_path.is_dir():
        log_error(f"Service directory '{service}' does not exist")
        return False
    if not (service_path / ".service").exists():
        log_error(f"Service '{service}' missing .service file")
        return False
    return True


def run_ssh_command(command: str) -> Tuple[bool, str]:
    """Run command on remote server via SSH."""
    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", SSH_HOST, command],
            check=True,
            capture_output=True,
            text=True,
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr


def copy_file_ssh(local_path: str, remote_path: str) -> bool:
    """Copy file to remote server via SCP."""
    try:
        subprocess.run(
            [
                "scp",
                "-o",
                "StrictHostKeyChecking=no",
                local_path,
                f"{SSH_HOST}:{remote_path}",
            ],
            check=True,
            capture_output=True,
        )
        return True
    except subprocess.CalledProcessError:
        return False


def install_checker_local(service: str) -> bool:
    """Install checker for a service (local installation)."""
    service_path = Path(service)
    checker_dir = Path(CHECKER_BASE_DIR) / service

    log_info(f"Installing checker for service: {service}")

    try:
        # Create checker directory
        checker_dir.mkdir(parents=True, exist_ok=True)

        # Copy checker.py
        shutil.copy2(service_path / "checker.py", checker_dir)
        log_info(f"Copied checker.py to {checker_dir}/")

        # Copy checker.sh if it exists
        checker_sh = service_path / "checker.sh"
        if checker_sh.exists():
            shutil.copy2(checker_sh, checker_dir)
            os.chmod(checker_dir / "checker.sh", 0o755)
            log_info(f"Copied checker.sh to {checker_dir}/ and made it executable")
        else:
            log_warning(f"No checker.sh found for {service} (optional file)")

        # Create config directory and copy .env file
        config_dir = Path(CHECKER_CONFIG_DIR)
        config_dir.mkdir(parents=True, exist_ok=True)

        env_file = find_env_file(service_path)
        if env_file:
            shutil.copy2(env_file, config_dir)
            log_info(f"Copied {env_file.name} to {config_dir}/")
            os.chmod(config_dir / env_file.name, 0o644)

        # Set ownership recursively
        shutil.chown(checker_dir, user=CHECKER_USER, group=CHECKER_USER)
        for root, dirs, files in os.walk(checker_dir):
            for d in dirs:
                shutil.chown(
                    os.path.join(root, d), user=CHECKER_USER, group=CHECKER_USER
                )
            for f in files:
                shutil.chown(
                    os.path.join(root, f), user=CHECKER_USER, group=CHECKER_USER
                )

        log_info(f"Set ownership of {checker_dir} to {CHECKER_USER}")

        # Set appropriate permissions
        os.chmod(checker_dir, 0o755)
        os.chmod(checker_dir / "checker.py", 0o644)
        if (checker_dir / "checker.sh").exists():
            os.chmod(checker_dir / "checker.sh", 0o755)

        log_success(f"Successfully installed checker for {service}")
        return True

    except Exception as e:
        log_error(f"Failed to install checker for {service}: {e}")
        return False


def install_checker_remote_from_tar(
    service: str, checker_tar_local_path: Path, env_local_path: Optional[Path]
) -> bool:
    """Upload checker tar, extract to /opt/checker/<service>, copy env, chown, and setup venv if missing."""
    checker_dir = f"{CHECKER_BASE_DIR}/{service}"
    remote_tmp_dir = f"/tmp/{service}_deploy"
    remote_checker_tar = f"{remote_tmp_dir}/{checker_tar_local_path.name}"

    log_info(f"Installing checker for service {service} on remote server...")

    try:
        # Prepare remote directories
        ok, out = run_ssh_command(
            f"mkdir -p '{checker_dir}' '{remote_tmp_dir}' '{CHECKER_CONFIG_DIR}' '/root/packages/checker' '/root/packages/vulnbox'"
        )
        if not ok:
            log_error(f"Failed to create directories on remote server: {out}")
            return False

        # Upload checker tar to temporary directory
        if not copy_file_ssh(str(checker_tar_local_path), remote_checker_tar):
            log_error("Failed to upload checker tarball to remote server")
            return False

        # Extract checker tar into target directory
        ok, out = run_ssh_command(f"tar -xzf '{remote_checker_tar}' -C '{checker_dir}'")
        if not ok:
            log_error(f"Failed to extract checker tarball: {out}")
            return False

        # Upload and place env file
        if env_local_path and env_local_path.exists():
            remote_env_tmp = f"{remote_tmp_dir}/{service}.env"
            if not copy_file_ssh(str(env_local_path), remote_env_tmp):
                log_error("Failed to upload env file to remote server")
                return False
            ok, out = run_ssh_command(
                f"install -m 0644 '{remote_env_tmp}' '{CHECKER_CONFIG_DIR}/{service}.env'"
            )
            if not ok:
                log_error(f"Failed to place env file: {out}")
                return False
        else:
            log_warning(f"No env file found for {service}; skipping env install")

        # Ownership
        run_ssh_command(
            f"chown -R '{CHECKER_USER}:{CHECKER_USER}' '{CHECKER_BASE_DIR}'"
        )

        # Setup venv if missing
        created_env = False
        ok, _ = run_ssh_command("test -d '/opt/env'")
        if not ok:
            created_env = True
            ok, out = run_ssh_command("python3 -m venv /opt/env")
            if not ok:
                log_error(f"Failed to create /opt/env venv: {out}")
                return False
            # Link ctf_gameserver package into site-packages (Python 3.12 path per requirement)
            run_ssh_command(
                "ln -s /usr/lib/python3/dist-packages/ctf_gameserver /opt/env/lib/python3.12/site-packages/"
            )

        # Only install requirements when creating a new env
        if created_env:
            # If requirements exist inside extracted checker
            req_path = f"{checker_dir}/requirements.txt"
            ok, _ = run_ssh_command(f"test -f '{req_path}'")
            if ok:
                ok, out = run_ssh_command(f"/opt/env/bin/pip install -r '{req_path}'")
                if not ok:
                    log_error(f"Failed to install checker requirements: {out}")
                    return False

        log_success(f"Successfully installed checker for {service} on remote server")
        return True
    except Exception as e:
        log_error(f"Failed to install checker for {service} on remote server: {e}")
        return False


def _matches_pattern(filepath: str, patterns: List[str]) -> bool:
    import fnmatch

    for pattern in patterns:
        if fnmatch.fnmatch(filepath, pattern) or fnmatch.fnmatch(
            os.path.basename(filepath), pattern
        ):
            return True
    return False


def _gather_files(
    include_patterns: List[str], exclude_patterns: List[str], base_dir: Path
) -> List[str]:
    files_to_pack: List[str] = []
    original_cwd = os.getcwd()
    os.chdir(base_dir)
    try:
        for pattern in include_patterns:
            if pattern.endswith("/"):
                dir_pattern = pattern.rstrip("/")
                if os.path.isdir(dir_pattern):
                    for root, dirs, files in os.walk(dir_pattern):
                        dirs[:] = [
                            d
                            for d in dirs
                            if not _matches_pattern(
                                os.path.join(root, d), exclude_patterns
                            )
                        ]
                        for file in files:
                            filepath = os.path.join(root, file)
                            if not _matches_pattern(filepath, exclude_patterns):
                                files_to_pack.append(filepath)
            else:
                if "*" in pattern or "?" in pattern:
                    import glob as _glob

                    for filepath in _glob.glob(pattern, recursive=True):
                        if os.path.isfile(filepath) and not _matches_pattern(
                            filepath, exclude_patterns
                        ):
                            files_to_pack.append(filepath)
                else:
                    if os.path.exists(pattern) and not _matches_pattern(
                        pattern, exclude_patterns
                    ):
                        files_to_pack.append(pattern)
    finally:
        os.chdir(original_cwd)
    return list(set(files_to_pack))


def _create_tar(
    files: List[str],
    output_path: Path,
    base_dir: Path,
    vulnbox: bool = False,
    vulnbox_dir: Optional[str] = None,
) -> bool:
    mode = "w:gz"
    original_cwd = os.getcwd()
    try:
        with tarfile.open(output_path, mode) as tar:
            os.chdir(base_dir)
            for filepath in files:
                if os.path.exists(filepath):
                    if vulnbox and vulnbox_dir:
                        arcname = os.path.join(vulnbox_dir, filepath)
                        tar.add(filepath, arcname=arcname)
                    else:
                        tar.add(filepath)
        return True
    except Exception as e:
        log_error(f"Error creating {output_path}: {e}")
        return False
    finally:
        os.chdir(original_cwd)


def _load_service_config(config_path: Path) -> Optional[dict]:
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        log_error(f"Error loading {config_path}: {e}")
        return None


def build_packages_for_service(service: str) -> Optional[Tuple[Path, Path, str]]:
    """Build checker and vulnbox tarballs for a service using its config.json.
    Returns (checker_tar_path, vulnbox_tar_path, service_name) on success, else None.
    """
    service_path = Path(service)
    config_path = service_path / "config.json"

    cfg = _load_service_config(config_path)
    if not cfg:
        # Fallback to repository-level config.json
        repo_cfg_path = Path.cwd() / "config.json"
        cfg = _load_service_config(repo_cfg_path)
        if not cfg:
            log_error(f"No usable config.json found for {service}")
            return None

    # Always name tarballs after directory name to avoid collisions
    service_name = service_path.name
    vulnbox_cfg = cfg.get("vulnbox", {})
    checker_cfg = cfg.get("checker", {})
    vulnbox_dir_template = cfg.get("vulnbox_directory", f"{service_name}")
    vulnbox_dirname = vulnbox_dir_template.format(service_name=service_name)

    # Resolve output paths
    Path(PACKAGE_CHECKER_DIR).mkdir(parents=True, exist_ok=True)
    Path(PACKAGE_VULNBOX_DIR).mkdir(parents=True, exist_ok=True)
    checker_out = Path(PACKAGE_CHECKER_DIR) / f"{service_name}_ch.tar.gz"
    vulnbox_out = Path(PACKAGE_VULNBOX_DIR) / f"{service_name}_vb.tar.gz"

    # Gather file lists
    vulnbox_files = _gather_files(
        vulnbox_cfg.get("files", []), vulnbox_cfg.get("exclude", []), service_path
    )
    checker_files = _gather_files(
        checker_cfg.get("files", []), checker_cfg.get("exclude", []), service_path
    )

    if not vulnbox_files:
        log_warning(f"No vulnbox files matched for {service}")
    if not checker_files:
        log_warning(f"No checker files matched for {service}")

    ok1 = (
        _create_tar(
            vulnbox_files,
            vulnbox_out,
            service_path,
            vulnbox=True,
            vulnbox_dir=vulnbox_dirname,
        )
        if vulnbox_files
        else True
    )
    ok2 = (
        _create_tar(checker_files, checker_out, service_path, vulnbox=False)
        if checker_files
        else True
    )
    if ok1 and ok2:
        log_success(f"Built: {checker_out}")
        log_success(f"Built: {vulnbox_out}")
        return checker_out, vulnbox_out, service_name
    return None


def show_usage():
    """Show usage information."""
    print(
        f"""
CTF Challenge Packaging & Deployment Script

USAGE:
    python3 main.py [OPTIONS] [SERVICE...]

OPTIONS:
    --server-install    Upload packages and install checkers on remote gameserver via SSH
    --help, -h          Show this help message

ARGUMENTS:
    SERVICE             Specific service name(s) to process
                       If not specified, all services with a .service file will be processed

BEHAVIOR:
    - Builds both checker and vulnbox packages using each service's config.json
    - Outputs to packages/checker and packages/vulnbox
    - With --server-install, uploads tarballs and installs checkers remotely on {SSH_HOST}

REMOTE SERVER STEPS:
    - mkdir -p /opt/checker/<service> and extract checker there
    - copy <service>.env to {CHECKER_CONFIG_DIR}/<service>.env
    - chown -R {CHECKER_USER}:{CHECKER_USER} {CHECKER_BASE_DIR}
    - create /opt/env if missing, link ctf_gameserver, pip install requirements on first creation
"""
    )


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="CTF Challenge Packaging & Deployment Script", add_help=False
    )
    parser.add_argument(
        "--server-install",
        action="store_true",
        help="Upload packages and install checkers on remote gameserver via SSH",
    )
    parser.add_argument(
        "--help", "-h", action="store_true", help="Show this help message"
    )
    parser.add_argument(
        "services", nargs="*", help="Specific service name(s) to process"
    )

    args = parser.parse_args()

    if args.help:
        show_usage()
        return

    log_info("CTF Challenge Packaging & Deployment Script")
    log_info(f"Server install mode: {'enabled' if args.server_install else 'disabled'}")

    if args.server_install:
        check_ssh_connectivity()

    # Determine services to process
    if args.services:
        services = [
            s
            for s in args.services
            if (Path(s).is_dir() and (Path(s) / ".service").exists())
        ]
        skipped = set(args.services) - set(services)
        for s in skipped:
            log_warning(f"Skipping '{s}' (not a directory or missing .service)")
    else:
        services = get_services_with_service_file()

    if not services:
        log_warning("No services with a .service file found in current directory")
        return

    log_info(f"Services to process: {' '.join(services)}")

    build_map: List[Tuple[str, Optional[Tuple[Path, Path, str]]]] = []
    success_count = 0
    error_count = 0

    # Build packages for each service
    for service in services:
        print()
        log_info(f"Packaging service: {service}")
        if not validate_service_for_packaging(service):
            error_count += 1
            build_map.append((service, None))
            continue
        result = build_packages_for_service(service)
        build_map.append((service, result))
        if result is None:
            log_error(f"Packaging failed for {service}")
            error_count += 1
        else:
            success_count += 1

    # If server install, upload and install checkers
    if args.server_install:
        for service, result in build_map:
            if result is None:
                continue
            checker_tar, vulnbox_tar, service_name = result
            # Upload tarballs to a holding directory
            run_ssh_command("mkdir -p /root/packages/checker /root/packages/vulnbox")
            copy_file_ssh(
                str(checker_tar), f"/root/packages/checker/{checker_tar.name}"
            )
            copy_file_ssh(
                str(vulnbox_tar), f"/root/packages/vulnbox/{vulnbox_tar.name}"
            )

            env_path = find_env_file(Path(service))
            ok = install_checker_remote_from_tar(service, checker_tar, env_path)
            if not ok:
                error_count += 1
                continue

            # Execute optional post-install commands from config.json
            cfg = _load_service_config(
                Path(service) / "config.json"
            ) or _load_service_config(Path.cwd() / "config.json")
            post_install = []
            if cfg and isinstance(cfg.get("post_install"), list):
                post_install = cfg.get("post_install")
            elif cfg and isinstance(cfg.get("post_install"), str):
                post_install = [cfg.get("post_install")]

            for cmd in post_install:
                if not isinstance(cmd, str) or not cmd.strip():
                    continue
                log_info(f"Running post-install on remote: {cmd}")
                ok_cmd, out = run_ssh_command(f"bash -lc {shlex.quote(cmd)}")
                if not ok_cmd:
                    log_error(f"Post-install command failed: {out}")
                    error_count += 1

    # Summary
    print()
    log_info("=== SUMMARY ===")
    log_success(f"Packaged successfully: {success_count}")
    if error_count > 0:
        log_error(f"Errors: {error_count}")
        if args.server_install:
            sys.exit(1)
    else:
        log_success("All operations completed successfully!")

    # Show created packages
    if Path(PACKAGE_DIR).exists():
        print()
        log_info(f"Packages under: {PACKAGE_DIR}")
        try:
            for sub in [PACKAGE_CHECKER_DIR, PACKAGE_VULNBOX_DIR]:
                for package in sorted(Path(sub).glob("*.tar.gz")):
                    size = package.stat().st_size
                    size_str = (
                        f"{size / 1024:.1f}K"
                        if size < 1024 * 1024
                        else f"{size / (1024*1024):.1f}M"
                    )
                    print(f"  {package.relative_to(PACKAGE_DIR)} ({size_str})")
        except Exception:
            pass


if __name__ == "__main__":
    main()
