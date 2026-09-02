#!/bin/sh

set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required. Install and start Docker Desktop, then try again."
    exit 1
fi

if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example. Fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, then run this script again."
    exit 1
fi

telegram_token=$(sed -n 's/^TELEGRAM_BOT_TOKEN=//p' .env | tail -n 1)
telegram_chat_id=$(sed -n 's/^TELEGRAM_CHAT_ID=//p' .env | tail -n 1)
if [ -z "$telegram_token" ] || [ "$telegram_token" = "your-bot-token-here" ] ||
    [ -z "$telegram_chat_id" ] || [ "$telegram_chat_id" = "your-chat-id-here" ]; then
    echo "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env, then run this script again."
    exit 1
fi

if [ ! -f state.json ]; then
    printf '%s\n' '{"last_block": 0, "known_pairs": {}, "new_pairs_this_session": []}' > state.json
fi

echo "Building the Docker image..."
docker compose build

echo "Running decoder tests in the container..."
docker compose run --rm monitor python test_decoder.py

echo "Starting the monitor. Press Ctrl+C to stop it."
docker compose up --remove-orphans