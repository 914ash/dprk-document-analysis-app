#!/usr/bin/env bash
set -euo pipefail

print_help() {
  cat <<'EOF'
DPRK Sanctions Toolkit

Commands:
  er <cmd>       Entity-resolution CLI
  drift <cmd>    Network-drift CLI
  api            Start the entity-resolution API
  test [er|drift|all]
  evals [er|drift|all]
  shell
  help
EOF
}

case "${1:-help}" in
  er)
    shift
    exec python -m dprk_er.cli "$@"
    ;;
  drift)
    shift
    exec python -m dprk_drift.cli "$@"
    ;;
  api)
    shift
    exec uvicorn dprk_er.api.app:app --host 0.0.0.0 --port "${API_PORT:-8000}" "$@"
    ;;
  test)
    shift
    project="${1:-all}"
    if [ "$project" = "er" ] || [ "$project" = "p1" ]; then
      cd /workspace/packages/entity-resolution
      exec python -m pytest tests/ -v --tb=short
    elif [ "$project" = "drift" ] || [ "$project" = "p2" ]; then
      cd /workspace/packages/network-drift
      exec python -m pytest tests/ -v --tb=short
    else
      cd /workspace/packages/entity-resolution
      python -m pytest tests/ -v --tb=short
      cd /workspace/packages/network-drift
      exec python -m pytest tests/ -v --tb=short
    fi
    ;;
  evals)
    shift
    project="${1:-all}"
    if [ "$project" = "er" ] || [ "$project" = "p1" ]; then
      cd /workspace/packages/entity-resolution
      exec python -m pytest evals/ -v --tb=short
    elif [ "$project" = "drift" ] || [ "$project" = "p2" ]; then
      cd /workspace/packages/network-drift
      exec python -m pytest evals/ -v --tb=short
    else
      cd /workspace/packages/entity-resolution
      python -m pytest evals/ -v --tb=short
      cd /workspace/packages/network-drift
      exec python -m pytest evals/ -v --tb=short
    fi
    ;;
  shell)
    exec /bin/bash
    ;;
  help|--help|-h)
    print_help
    ;;
  *)
    exec "$@"
    ;;
esac
