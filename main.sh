#!/bin/bash

# CTF Challenge Deployment Script
# Usage: ./deploy_challenges.sh [--package] [service_name...]
# 
# Options:
#   --package    Package challenges for distribution (excludes checker.py and .git)
#   service_name Specific service(s) to process (default: all services)

set -euo pipefail

# Configuration
CHECKER_BASE_DIR="/opt/checker"
CHECKER_CONFIG_DIR="/etc/ctf-gameserver/checker"
CHECKER_USER="ctf-checkerrunner"
PACKAGE_DIR="./packages"
SSH_HOST="root@x3ero0.dev"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root for installation operations
check_root() {
    if [[ $EUID -ne 0 && "$PACKAGE_ONLY" == false && "$SERVER_INSTALL" == false ]]; then
        log_error "This script must be run as root for local checker installation"
        log_info "Use 'sudo $0' or run with --package or --server-install option only"
        exit 1
    fi
}

# Check if user exists (for local installation)
check_user_exists() {
    local user="$1"
    if ! id "$user" &>/dev/null; then
        log_error "User '$user' does not exist"
        log_info "Please create the user first: sudo useradd -r -s /bin/false $user"
        exit 1
    fi
}

# Get all service directories (excluding those with .notaservice file)
get_services() {
    local services=()
    while IFS= read -r -d '' dir; do
        local dirname=$(basename "$dir")
        # Skip packages directory and any directory with .notaservice file
        if [[ "$dirname" != "packages" && ! -f "$dir/.notaservice" ]]; then
            services+=("$dirname")
        fi
    done < <(find . -maxdepth 1 -type d -not -path . -not -path ./.git -print0)
    
    # Sort and print the services
    printf '%s\n' "${services[@]}" | sort
}

# Validate service directory
validate_service() {
    local service="$1"
    
    if [[ ! -d "$service" ]]; then
        log_error "Service directory '$service' does not exist"
        return 1
    fi
    
    if [[ "$PACKAGE_ONLY" == false ]]; then
        if [[ ! -f "$service/checker.py" ]]; then
            log_error "Service '$service' missing checker.py"
            return 1
        fi
        
        # Check for any .env file
        local env_files
        env_files=$(find "$service" -maxdepth 1 -name "*.env" -type f)
        if [[ -z "$env_files" ]]; then
            log_error "Service '$service' missing .env file (no *.env files found)"
            return 1
        fi
        
        # Check if multiple .env files exist
        local env_count
        env_count=$(echo "$env_files" | wc -l)
        if [[ $env_count -gt 1 ]]; then
            log_warning "Service '$service' has multiple .env files:"
            echo "$env_files"
            log_info "Will use the first one found"
        fi
    fi
    
    return 0
}

# Check SSH connectivity to gameserver
check_ssh_connectivity() {
    log_info "Testing SSH connectivity to $SSH_HOST..."
    
    # Try SSH connection with the same options as terminal
    local ssh_output
    ssh_output=$(ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$SSH_HOST" "echo 'SSH connection successful'" 2>&1)
    local ssh_exit_code=$?
    
    if [[ $ssh_exit_code -ne 0 ]]; then
        log_error "Cannot connect to $SSH_HOST via SSH (exit code: $ssh_exit_code)"
        log_error "SSH output: $ssh_output"
        log_info "Please ensure:"
        log_info "  1. SSH key authentication is set up"
        log_info "  2. Host $SSH_HOST is reachable"
        log_info "  3. You have root access on the server"
        log_info "  4. Your SSH config is properly set up"
        log_info "Manual test command: ssh $SSH_HOST 'echo test'"
        exit 1
    fi
    
    log_success "SSH connectivity verified"
}

# Install checker on remote server via SSH
install_checker_remote() {
    local service="$1"
    local checker_dir="${CHECKER_BASE_DIR}/${service}"
    
    log_info "Installing checker for service $service on remote server..."
    
    # Create checker directory on remote server
    ssh -o StrictHostKeyChecking=no "$SSH_HOST" "mkdir -p '$checker_dir'"
    log_info "Created directory $checker_dir on remote server"
    
    # Copy checker.py
    scp -o StrictHostKeyChecking=no "$service/checker.py" "$SSH_HOST:$checker_dir/"
    log_info "Copied checker.py to remote server"
    
    # Copy checker.sh if it exists
    if [[ -f "$service/checker.sh" ]]; then
        scp -o StrictHostKeyChecking=no "$service/checker.sh" "$SSH_HOST:$checker_dir/"
        log_info "Copied checker.sh to remote server"
    else
        log_warning "No checker.sh found for $service (optional file)"
    fi
    
    # Make scripts executable on remote server
    ssh -o StrictHostKeyChecking=no "$SSH_HOST" "chmod 755 '$checker_dir'/*.py '$checker_dir'/*.sh 2>/dev/null || true"
    log_info "Made scripts executable on remote server"
    
    # Create config directory and copy .env file
    ssh -o StrictHostKeyChecking=no "$SSH_HOST" "mkdir -p '$CHECKER_CONFIG_DIR'"
    
    # Find and copy the .env file
    local env_file
    env_file=$(find "$service" -maxdepth 1 -name "*.env" -type f | head -n 1)
    if [[ -n "$env_file" ]]; then
        scp -o StrictHostKeyChecking=no "$env_file" "$SSH_HOST:$CHECKER_CONFIG_DIR/"
        local env_filename
        env_filename=$(basename "$env_file")
        log_info "Copied $env_filename to remote server"
    fi
    
    # Set ownership on remote server
    ssh -o StrictHostKeyChecking=no "$SSH_HOST" "chown -R '$CHECKER_USER:$CHECKER_USER' '$CHECKER_BASE_DIR'"
    log_info "Set ownership of $CHECKER_BASE_DIR to $CHECKER_USER on remote server"
    
    # Enable or restart checkermaster service
    local service_name="checkermaster@${service}.service"
    
    # Check if service exists (is enabled or has been created)
    if ssh -o StrictHostKeyChecking=no "$SSH_HOST" "systemctl list-unit-files '$service_name' | grep -q '$service_name'"; then
        log_info "Service $service_name exists, restarting..."
        ssh -o StrictHostKeyChecking=no "$SSH_HOST" "systemctl restart '$service_name'"
        log_success "Restarted $service_name"
    else
        log_info "Service $service_name doesn't exist, enabling and starting..."
        ssh -o StrictHostKeyChecking=no "$SSH_HOST" "systemctl enable '$service_name' && systemctl start '$service_name'"
        log_success "Enabled and started $service_name"
    fi
    
    log_success "Successfully installed checker for $service on remote server"
}
# Install checker for a service (local installation)
install_checker() {
    local service="$1"
    local checker_dir="${CHECKER_BASE_DIR}/${service}"
    
    log_info "Installing checker for service: $service"
    
    # Create checker directory
    mkdir -p "$checker_dir"
    
    # Copy checker.py
    cp "$service/checker.py" "$checker_dir/"
    log_info "Copied checker.py to $checker_dir/"
    
    # Copy checker.sh if it exists
    if [[ -f "$service/checker.sh" ]]; then
        cp "$service/checker.sh" "$checker_dir/"
        chmod +x "$checker_dir/checker.sh"
        log_info "Copied checker.sh to $checker_dir/ and made it executable"
    else
        log_warning "No checker.sh found for $service (optional file)"
    fi
    
    # Create config directory if it doesn't exist
    mkdir -p "$CHECKER_CONFIG_DIR"
    
    # Copy service.env
    cp "$service/service.env" "$CHECKER_CONFIG_DIR/"
    log_info "Copied service.env to $CHECKER_CONFIG_DIR/"
    
    # Set ownership recursively
    chown -R "${CHECKER_USER}:${CHECKER_USER}" "$checker_dir"
    log_info "Set ownership of $checker_dir to $CHECKER_USER"
    
    # Set appropriate permissions
    chmod 755 "$checker_dir"
    chmod 644 "$checker_dir/checker.py"
    if [[ -f "$checker_dir/checker.sh" ]]; then
        chmod 755 "$checker_dir/checker.sh"
    fi
    
    log_success "Successfully installed checker for $service"
}

# Package service for distribution
package_service() {
    local service="$1"
    local package_file="${PACKAGE_DIR}/${service}.tar.gz"
    
    log_info "Packaging service: $service"
    
    # Check if service should be ignored
    if [[ -f "$service/.notaservice" ]]; then
        log_warning "Skipping $service (contains .notaservice file)"
        return 0
    fi
    
    # Create package directory
    mkdir -p "$PACKAGE_DIR"
    
    # Create absolute path for package file
    local abs_package_file
    abs_package_file=$(realpath "$package_file")
    
    # Use rsync to copy with exclusions
    tar -czf "$abs_package_file" \
        --exclude="$service/checker.py" \
        --exclude="$service/checker.sh" \
        --exclude="$service/exploits" \
        --exclude="$service/.git" \
        --exclude="$service/.gitignore" \
        --exclude="$service/.DS_Store" \
        --exclude="$service/__pycache__" \
        --exclude="$service/*.pyc" \
        --exclude="$service/.notaservice" \
        "$service"
    
    # Verify the package was created and get file size
    if [[ -f "$package_file" ]]; then
        local size
        size=$(du -h "$package_file" | cut -f1)
        log_success "Created package: $package_file ($size)"
        return 0
    else
        log_error "Failed to create package: $package_file"
        return 1
    fi
}

# Show usage information
show_usage() {
    cat << EOF
CTF Challenge Deployment Script

USAGE:
    $0 [OPTIONS] [SERVICE...]

OPTIONS:
    --package           Package challenges for distribution only
    --server-install    Install checkers on remote gameserver via SSH
    --help, -h          Show this help message

ARGUMENTS:
    SERVICE             Specific service name(s) to process
                       If not specified, all services will be processed

EXAMPLES:
    # Install all checkers locally
    sudo $0

    # Install specific checker locally
    sudo $0 ping

    # Install all checkers on remote gameserver
    $0 --server-install

    # Install specific checker on remote gameserver
    $0 --server-install ping

    # Package all services for distribution
    $0 --package

    # Package specific service
    $0 --package QFQ_Note

    # Install checker locally and package service
    sudo $0 ping && $0 --package ping

DIRECTORY STRUCTURE:
    Each service directory should contain:
    - checker.py        (for checker installation)
    - checker.sh        (optional, for checker installation)
    - *.env             (any .env file for checker configuration)
    - Other files       (will be included in package)

REMOTE SERVER:
    SSH Host: $SSH_HOST
    Requires SSH key authentication and root access

INSTALLATION PATHS:
    Checkers: $CHECKER_BASE_DIR/<service>/checker.py
    Scripts:  $CHECKER_BASE_DIR/<service>/checker.sh (if present)
    Configs:  $CHECKER_CONFIG_DIR/<filename>.env
    Services: checkermaster@<service>.service

EOF
}

# Parse command line arguments
PACKAGE_ONLY=false
SERVER_INSTALL=false
SERVICES=()

while [[ $# -gt 0 ]]; do
    case $1 in
        --package)
            PACKAGE_ONLY=true
            shift
            ;;
        --server-install)
            SERVER_INSTALL=true
            shift
            ;;
        --help|-h)
            show_usage
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            SERVICES+=("$1")
            shift
            ;;
    esac
done

# Main execution
main() {
    log_info "CTF Challenge Deployment Script"
    log_info "Package mode: $([ "$PACKAGE_ONLY" == true ] && echo "enabled" || echo "disabled")"
    log_info "Server install mode: $([ "$SERVER_INSTALL" == true ] && echo "enabled" || echo "disabled")"
    
    # Check prerequisites
    if [[ "$PACKAGE_ONLY" == false && "$SERVER_INSTALL" == false ]]; then
        check_root
        check_user_exists "$CHECKER_USER"
    elif [[ "$SERVER_INSTALL" == true ]]; then
        check_ssh_connectivity
    fi
    
    # Determine which services to process
    if [[ ${#SERVICES[@]} -eq 0 ]]; then
        log_info "No specific services specified, processing all services"
        readarray -t SERVICES < <(get_services)
    fi
    
    if [[ ${#SERVICES[@]} -eq 0 ]]; then
        log_warning "No services found in current directory"
        exit 0
    fi
    
    log_info "Services to process: ${SERVICES[*]}"
    
    # Process each service
    local success_count=0
    local error_count=0
    
    for service in "${SERVICES[@]}"; do
        echo
        log_info "Processing service: $service"
        
        if ! validate_service "$service"; then
            error_count=$((error_count + 1))
            continue
        fi
        
        # Install checker if not package-only mode
        if [[ "$PACKAGE_ONLY" == false ]]; then
            if [[ "$SERVER_INSTALL" == true ]]; then
                if install_checker_remote "$service"; then
                    log_success "Remote checker installation completed for $service"
                else
                    log_error "Remote checker installation failed for $service"
                    error_count=$((error_count + 1))
                    continue
                fi
            else
                if install_checker "$service"; then
                    log_success "Local checker installation completed for $service"
                else
                    log_error "Local checker installation failed for $service"
                    error_count=$((error_count + 1))
                    continue
                fi
            fi
        fi
        
        # Package service (only if not server-install mode)
        if [[ "$SERVER_INSTALL" == false ]]; then
            if package_service "$service"; then
                log_success "Packaging completed for $service"
            else
                log_error "Packaging failed for $service"
                error_count=$((error_count + 1))
                continue
            fi
        fi
        
        success_count=$((success_count + 1))
        log_info "Finished processing $service, moving to next service..."
    done
    
    # Summary
    echo
    log_info "=== DEPLOYMENT SUMMARY ==="
    log_success "Successfully processed: $success_count services"
    if [[ $error_count -gt 0 ]]; then
        log_error "Failed to process: $error_count services"
        exit 1
    else
        log_success "All services processed successfully!"
    fi
    
    if [[ -d "$PACKAGE_DIR" ]]; then
        echo
        log_info "Package files created in: $PACKAGE_DIR"
        ls -la "$PACKAGE_DIR"
    fi
}

# Run main function
main
