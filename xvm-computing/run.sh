#!/bin/bash

# Password Manager Helper Script
# Usage: ./run.sh [command]

set -e

COMPOSE_FILE="docker compose.yml"
SERVICE_NAME="xvm"

case "$1" in
"start")
    docker compose up -d
    echo "started on localhost:7777"
    echo "Use './run.sh logs' to view logs"
    ;;

"stop")
    docker compose down
    ;;

"restart")
    docker compose restart
    ;;

"logs")
    echo "Showing service logs (Ctrl+C to exit)..."
    docker compose logs -f
    ;;

"shell")
    echo "Opening shell in container..."
    docker compose exec $SERVICE_NAME /bin/bash
    ;;

"build")
    echo "Building password manager image..."
    docker compose build
    echo "Build complete"
    ;;

"clean")
    echo "Cleaning up containers and volumes..."
    docker compose down -v
    docker system prune -f
    echo "Cleanup complete"
    ;;

"status")
    echo "Service status:"
    docker compose ps
    ;;

"help" | "--help" | "-h" | "")
    echo "XVM-Computing Helper Script"
    echo ""
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start     - Start the password manager service"
    echo "  stop      - Stop the service"
    echo "  restart   - Restart the service"
    echo "  logs      - Show service logs"
    echo "  shell     - Open shell in container"
    echo "  build     - Build the Docker image"
    echo "  clean     - Clean up containers and volumes"
    echo "  status    - Show service status"
    echo "  help      - Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./run.sh start    # Start the service"
    echo "  ./run.sh logs     # View logs"
    echo "  ./run.sh test     # Run tests"
    echo "  ./run.sh stop     # Stop the service"
    ;;

*)
    echo "Error: Unknown command '$1'"
    echo "Use './run.sh help' to see available commands"
    exit 1
    ;;
esac
