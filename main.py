#!/usr/bin/env python3
"""
CTF Challenge Deployment Script
Usage: python deploy_challenges.py [OPTIONS] [SERVICE...]

Options:
  --package           Package challenges for distribution only
  --server-install    Install checkers on remote gameserver via SSH
  --help, -h          Show this help message
"""

import os
import sys
import argparse
import subprocess
import shutil
import glob
import tarfile
from pathlib import Path
from typing import List, Optional, Tuple

# Configuration
CHECKER_BASE_DIR = "/opt/checker"
CHECKER_CONFIG_DIR = "/etc/ctf-gameserver/checker"
CHECKER_USER = "ctf-checkerrunner"
PACKAGE_DIR = "./packages"
SSH_HOST = "root@x3ero0.dev"

# Colors for output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

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
        log_info("Use 'sudo python3 deploy_challenges.py' or run with --package or --server-install option only")
        sys.exit(1)

def check_user_exists(user: str) -> None:
    """Check if user exists (for local installation)."""
    try:
        subprocess.run(['id', user], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        log_error(f"User '{user}' does not exist")
        log_info(f"Please create the user first: sudo useradd -r -s /bin/false {user}")
        sys.exit(1)

def check_ssh_connectivity() -> None:
    """Check SSH connectivity to gameserver."""
    log_info(f"Testing SSH connectivity to {SSH_HOST}...")
    
    try:
        result = subprocess.run([
            'ssh', '-o', 'ConnectTimeout=10', 
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            SSH_HOST, "echo 'SSH connection successful'"
        ], check=True, capture_output=True, text=True)
        
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

def get_services() -> List[str]:
    """Get all service directories (excluding those with .notaservice file)."""
    services = []
    
    for item in Path('.').iterdir():
        if item.is_dir() and item.name not in ['.git', 'packages']:
            if not (item / '.notaservice').exists():
                services.append(item.name)
    
    return sorted(services)

def find_env_file(service_dir: Path) -> Optional[Path]:
    """Find the .env file in service directory."""
    env_files = list(service_dir.glob('*.env'))
    
    if not env_files:
        return None
    
    if len(env_files) > 1:
        log_warning(f"Service '{service_dir.name}' has multiple .env files:")
        for env_file in env_files:
            print(f"  {env_file}")
        log_info("Will use the first one found")
    
    return env_files[0]

def validate_service(service: str, package_only: bool) -> bool:
    """Validate service directory."""
    service_path = Path(service)
    
    if not service_path.is_dir():
        log_error(f"Service directory '{service}' does not exist")
        return False
    
    if not package_only:
        # Check for checker.py
        if not (service_path / 'checker.py').exists():
            log_error(f"Service '{service}' missing checker.py")
            return False
        
        # Check for .env file
        env_file = find_env_file(service_path)
        if not env_file:
            log_error(f"Service '{service}' missing .env file (no *.env files found)")
            return False
    
    return True

def run_ssh_command(command: str) -> Tuple[bool, str]:
    """Run command on remote server via SSH."""
    try:
        result = subprocess.run([
            'ssh', '-o', 'StrictHostKeyChecking=no', 
            SSH_HOST, command
        ], check=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def copy_file_ssh(local_path: str, remote_path: str) -> bool:
    """Copy file to remote server via SCP."""
    try:
        subprocess.run([
            'scp', '-o', 'StrictHostKeyChecking=no',
            local_path, f"{SSH_HOST}:{remote_path}"
        ], check=True, capture_output=True)
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
        shutil.copy2(service_path / 'checker.py', checker_dir)
        log_info(f"Copied checker.py to {checker_dir}/")
        
        # Copy checker.sh if it exists
        checker_sh = service_path / 'checker.sh'
        if checker_sh.exists():
            shutil.copy2(checker_sh, checker_dir)
            os.chmod(checker_dir / 'checker.sh', 0o755)
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
                shutil.chown(os.path.join(root, d), user=CHECKER_USER, group=CHECKER_USER)
            for f in files:
                shutil.chown(os.path.join(root, f), user=CHECKER_USER, group=CHECKER_USER)
        
        log_info(f"Set ownership of {checker_dir} to {CHECKER_USER}")
        
        # Set appropriate permissions
        os.chmod(checker_dir, 0o755)
        os.chmod(checker_dir / 'checker.py', 0o644)
        if (checker_dir / 'checker.sh').exists():
            os.chmod(checker_dir / 'checker.sh', 0o755)
        
        log_success(f"Successfully installed checker for {service}")
        return True
        
    except Exception as e:
        log_error(f"Failed to install checker for {service}: {e}")
        return False

def install_checker_remote(service: str) -> bool:
    """Install checker on remote server via SSH."""
    service_path = Path(service)
    checker_dir = f"{CHECKER_BASE_DIR}/{service}"
    
    log_info(f"Installing checker for service {service} on remote server...")
    
    try:
        # Create checker directory on remote server
        success, _ = run_ssh_command(f"mkdir -p '{checker_dir}'")
        if not success:
            log_error(f"Failed to create directory {checker_dir} on remote server")
            return False
        log_info(f"Created directory {checker_dir} on remote server")
        
        # Copy checker.py
        if not copy_file_ssh(str(service_path / 'checker.py'), f"{checker_dir}/"):
            log_error("Failed to copy checker.py to remote server")
            return False
        log_info("Copied checker.py to remote server")
        
        # Copy checker.sh if it exists
        checker_sh = service_path / 'checker.sh'
        if checker_sh.exists():
            if not copy_file_ssh(str(checker_sh), f"{checker_dir}/"):
                log_error("Failed to copy checker.sh to remote server")
                return False
            log_info("Copied checker.sh to remote server")
        else:
            log_warning(f"No checker.sh found for {service} (optional file)")
        
        # Make scripts executable on remote server
        run_ssh_command(f"chmod 755 '{checker_dir}'/*.py '{checker_dir}'/*.sh 2>/dev/null || true")
        log_info("Made scripts executable on remote server")
        
        # Create config directory and copy .env file
        run_ssh_command(f"mkdir -p '{CHECKER_CONFIG_DIR}'")
        
        env_file = find_env_file(service_path)
        if env_file:
            if not copy_file_ssh(str(env_file), f"{CHECKER_CONFIG_DIR}/"):
                log_error(f"Failed to copy {env_file.name} to remote server")
                return False
            log_info(f"Copied {env_file.name} to remote server")
        
        # Set ownership on remote server
        run_ssh_command(f"chown -R '{CHECKER_USER}:{CHECKER_USER}' '{CHECKER_BASE_DIR}'")
        log_info(f"Set ownership of {CHECKER_BASE_DIR} to {CHECKER_USER} on remote server")
        
        # Enable or restart checkermaster service
        service_name = f"ctf-checkermaster@{service}.service"
        service_file_path = f"/etc/systemd/system/multi-user.target.wants/{service_name}"
        
        # Check if service file exists
        success, _ = run_ssh_command(f"test -f '{service_file_path}'")
        
        if success:
            log_info(f"Service {service_name} exists, restarting...")
            success, output = run_ssh_command(f"systemctl restart '{service_name}'")
            if success:
                log_success(f"Restarted {service_name}")
            else:
                log_error(f"Failed to restart {service_name}: {output}")
                return False
        else:
            log_info(f"Service {service_name} doesn't exist, enabling and starting...")
            success, output = run_ssh_command(f"systemctl enable '{service_name}' && systemctl start '{service_name}'")
            if success:
                log_success(f"Enabled and started {service_name}")
            else:
                log_error(f"Failed to enable/start {service_name}: {output}")
                return False
        
        log_success(f"Successfully installed checker for {service} on remote server")
        return True
        
    except Exception as e:
        log_error(f"Failed to install checker for {service} on remote server: {e}")
        return False

def package_service(service: str) -> bool:
    """Package service for distribution."""
    service_path = Path(service)
    package_file = Path(PACKAGE_DIR) / f"{service}.tar.gz"
    
    log_info(f"Packaging service: {service}")
    
    # Check if service should be ignored
    if (service_path / '.notaservice').exists():
        log_warning(f"Skipping {service} (contains .notaservice file)")
        return True
    
    try:
        # Create package directory
        package_file.parent.mkdir(exist_ok=True)
        
        # Create tar.gz archive excluding specific files/directories
        with tarfile.open(package_file, 'w:gz') as tar:
            def filter_func(tarinfo):
                # Exclude specific files and directories
                excludes = [
                    'checker.py', 'checker.sh', 'exploits', '.git', 
                    '.gitignore', '.DS_Store', '__pycache__', '.notaservice'
                ]
                
                path_parts = Path(tarinfo.name).parts
                if len(path_parts) > 1:  # Skip the service directory itself
                    filename = path_parts[1]
                    if filename in excludes or filename.endswith('.pyc'):
                        return None
                    # Exclude any .env files
                    if filename.endswith('.env'):
                        return None
                
                return tarinfo
            
            tar.add(service, filter=filter_func)
        
        # Get file size for confirmation
        size = package_file.stat().st_size
        size_str = f"{size / 1024:.1f}K" if size < 1024*1024 else f"{size / (1024*1024):.1f}M"
        
        log_success(f"Created package: {package_file} ({size_str})")
        return True
        
    except Exception as e:
        log_error(f"Failed to create package: {package_file} - {e}")
        return False

def show_usage():
    """Show usage information."""
    print(f"""
CTF Challenge Deployment Script

USAGE:
    python3 deploy_challenges.py [OPTIONS] [SERVICE...]

OPTIONS:
    --package           Package challenges for distribution only
    --server-install    Install checkers on remote gameserver via SSH
    --help, -h          Show this help message

ARGUMENTS:
    SERVICE             Specific service name(s) to process
                       If not specified, all services will be processed

EXAMPLES:
    # Install all checkers locally
    sudo python3 deploy_challenges.py

    # Install specific checker locally
    sudo python3 deploy_challenges.py ping

    # Install all checkers on remote gameserver
    python3 deploy_challenges.py --server-install

    # Install specific checker on remote gameserver
    python3 deploy_challenges.py --server-install ping

    # Package all services for distribution
    python3 deploy_challenges.py --package

    # Package specific service
    python3 deploy_challenges.py --package QFQ_Note

    # Install checker locally and package service
    sudo python3 deploy_challenges.py ping && python3 deploy_challenges.py --package ping

DIRECTORY STRUCTURE:
    Each service directory should contain:
    - checker.py        (for checker installation)
    - checker.sh        (optional, for checker installation)
    - *.env             (any .env file for checker configuration)
    - Other files       (will be included in package)

REMOTE SERVER:
    SSH Host: {SSH_HOST}
    Requires SSH key authentication and root access

INSTALLATION PATHS:
    Checkers: {CHECKER_BASE_DIR}/<service>/checker.py
    Scripts:  {CHECKER_BASE_DIR}/<service>/checker.sh (if present)
    Configs:  {CHECKER_CONFIG_DIR}/<filename>.env
    Services: /etc/systemd/system/multi-user.target.wants/ctf-checkermaster@<service>.service
""")

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description='CTF Challenge Deployment Script', add_help=False)
    parser.add_argument('--package', action='store_true', help='Package challenges for distribution only')
    parser.add_argument('--server-install', action='store_true', help='Install checkers on remote gameserver via SSH')
    parser.add_argument('--help', '-h', action='store_true', help='Show this help message')
    parser.add_argument('services', nargs='*', help='Specific service name(s) to process')
    
    args = parser.parse_args()
    
    if args.help:
        show_usage()
        return
    
    log_info("CTF Challenge Deployment Script")
    log_info(f"Package mode: {'enabled' if args.package else 'disabled'}")
    log_info(f"Server install mode: {'enabled' if args.server_install else 'disabled'}")
    
    # Check prerequisites
    if not args.package and not args.server_install:
        check_root()
        check_user_exists(CHECKER_USER)
    elif args.server_install:
        check_ssh_connectivity()
    
    # Determine which services to process
    if not args.services:
        log_info("No specific services specified, processing all services")
        services = get_services()
    else:
        services = args.services
    
    if not services:
        log_warning("No services found in current directory")
        return
    
    log_info(f"Services to process: {' '.join(services)}")
    
    # Process each service
    success_count = 0
    error_count = 0
    
    for service in services:
        print()
        log_info(f"Processing service: {service}")
        
        if not validate_service(service, args.package):
            error_count += 1
            continue
        
        # Install checker if not package-only mode
        if not args.package:
            if args.server_install:
                if install_checker_remote(service):
                    log_success(f"Remote checker installation completed for {service}")
                else:
                    log_error(f"Remote checker installation failed for {service}")
                    error_count += 1
                    continue
            else:
                if install_checker_local(service):
                    log_success(f"Local checker installation completed for {service}")
                else:
                    log_error(f"Local checker installation failed for {service}")
                    error_count += 1
                    continue
        
        # Package service (only if not server-install mode)
        if not args.server_install:
            if package_service(service):
                log_success(f"Packaging completed for {service}")
            else:
                log_error(f"Packaging failed for {service}")
                error_count += 1
                continue
        
        success_count += 1
        log_info(f"Finished processing {service}, moving to next service...")
    
    # Summary
    print()
    log_info("=== DEPLOYMENT SUMMARY ===")
    log_success(f"Successfully processed: {success_count} services")
    if error_count > 0:
        log_error(f"Failed to process: {error_count} services")
        sys.exit(1)
    else:
        log_success("All services processed successfully!")
    
    if Path(PACKAGE_DIR).exists():
        print()
        log_info(f"Package files created in: {PACKAGE_DIR}")
        try:
            for package in sorted(Path(PACKAGE_DIR).glob("*.tar.gz")):
                size = package.stat().st_size
                size_str = f"{size / 1024:.1f}K" if size < 1024*1024 else f"{size / (1024*1024):.1f}M"
                print(f"  {package.name} ({size_str})")
        except Exception:
            pass

if __name__ == "__main__":
    main()
