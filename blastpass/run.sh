#!/bin/bash

# Password Manager Helper Script
# Usage: ./run.sh [command]

set -e

COMPOSE_FILE="docker-compose.yml"
SERVICE_NAME="blastpass"

case "$1" in
"start")
    echo "Starting password manager service..."
    docker-compose up -d
    echo "Password manager started on http://localhost:3333"
    echo "Crypto frontend started on http://localhost:3334"
    echo "Use './run.sh logs' to view logs"
    ;;

"stop")
    echo "Stopping password manager service..."
    docker-compose down
    echo "Service stopped"
    ;;

"restart")
    echo "Restarting password manager service..."
    docker-compose restart
    echo "Service restarted"
    ;;

"logs")
    echo "Showing service logs (Ctrl+C to exit)..."
    docker-compose logs -f
    ;;

"test")
    echo "Running basic health check..."

    # Ensure service is running
    if ! docker-compose ps | grep -q "Up"; then
        echo "Starting service for testing..."
        docker-compose up -d
        sleep 5
    fi

    # Test health endpoints
    echo "Testing password manager health..."
    docker-compose exec $SERVICE_NAME curl -f http://localhost:3333/api/health
    echo "Testing crypto frontend health..."
    docker-compose exec $SERVICE_NAME curl -f http://localhost:3334/health
    ;;

"shell")
    echo "Opening shell in container..."
    docker-compose exec $SERVICE_NAME /bin/bash
    ;;

"build")
    echo "Building password manager image..."
    docker-compose build
    echo "Build complete"
    ;;

"clean")
    echo "Cleaning up containers and volumes..."
    docker-compose down -v
    docker system prune -f
    echo "Cleanup complete"
    ;;

"status")
    echo "Service status:"
    docker-compose ps
    ;;

"help" | "--help" | "-h" | "")
    echo "Password Manager Helper Script"
    echo ""
    echo "Usage: ./run.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start     - Start the password manager service"
    echo "  stop      - Stop the service"
    echo "  restart   - Restart the service"
    echo "  logs      - Show service logs"
    echo "  test      - Run the test suite"
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
