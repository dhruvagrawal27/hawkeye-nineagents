#!/usr/bin/env bash
# Idempotent. Run inside the kafka container or via:
#   docker compose exec kafka /bin/bash /create-topics.sh
set -euo pipefail
BROKER="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"

kafka-topics --bootstrap-server "$BROKER" --create --if-not-exists \
  --topic hawkeye.events \
  --partitions 3 --replication-factor 1 \
  --config retention.ms=86400000

kafka-topics --bootstrap-server "$BROKER" --list
