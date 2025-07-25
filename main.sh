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
    if [[ $EUID -ne 0 && "$PACKAGE_ONLY" == false ]]; then
        log_error "This script must be run as root for checker installation"
        log_info "Use 'sudo $0' or run with --package option only"
        exit 1
    fi
}

# Check if user exists
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

        if [[ ! -f "$service/service.env" ]]; then
            log_error "Service '$service' missing service.env"
            return 1
        fi
    fi

    return 0
}

# Install checker for a service
install_checker() {
    local service="$1"
    local checker_dir="${CHECKER_BASE_DIR}/${service}"

    log_info "Installing checker for service: $service"

    # Create checker directory
    mkdir -p "$checker_dir"

    # Copy checker.py
    cp "$service/checker.py" "$checker_dir/"
    log_info "Copied checker.py to $checker_dir/"

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
    chmod 644 "$CHECKER_CONFIG_DIR/service.env"

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

    # Create tar.gz archive directly from source, excluding specific files/directories
    tar -czf "$abs_package_file" \
        --exclude="$service/checker.py" \
        --exclude="$service/exploits" \
        --exclude="$service/.git" \
        --exclude="$service/.gitignore" \
        --exclude="$service/.DS_Store" \
        --exclude="$service/__pycache__" \
        --exclude="$service/*.pyc" \
        --exclude="$service/.notaservice" \
        --exclude="$service/*.env" \
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
    cat <<EOF
CTF Challenge Deployment Script

USAGE:
    $0 [OPTIONS] [SERVICE...]

OPTIONS:
    --package           Package challenges for distribution only
    --help, -h          Show this help message

ARGUMENTS:
    SERVICE             Specific service name(s) to process
                       If not specified, all services will be processed

EXAMPLES:
    # Install all checkers
    sudo $0

    # Install specific checker
    sudo $0 ping

    # Package all services for distribution
    $0 --package

    # Package specific service
    $0 --package QFQ_Note

    # Install checker and package service
    sudo $0 ping && $0 --package ping

DIRECTORY STRUCTURE:
    Each service directory should contain:
    - checker.py        (for checker installation)
    - service.env       (for checker configuration)
    - Other files       (will be included in package)

INSTALLATION PATHS:
    Checkers: $CHECKER_BASE_DIR/<service>/checker.py
    Configs:  $CHECKER_CONFIG_DIR/service.env

EOF
}

# Parse command line arguments
PACKAGE_ONLY=false
SERVICES=()

while [[ $# -gt 0 ]]; do
    case $1 in
    --package)
        PACKAGE_ONLY=true
        shift
        ;;
    --help | -h)
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

    # Check prerequisites
    if [[ "$PACKAGE_ONLY" == false ]]; then
        check_root
        check_user_exists "$CHECKER_USER"
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
            if install_checker "$service"; then
                log_success "Checker installation completed for $service"
            else
                log_error "Checker installation failed for $service"
                error_count=$((error_count + 1))
                continue
            fi
        fi

        # Package service
        if package_service "$service"; then
            log_success "Packaging completed for $service"
        else
            log_error "Packaging failed for $service"
            error_count=$((error_count + 1))
            continue
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
