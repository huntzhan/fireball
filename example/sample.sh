#!/usr/bin/env bash
set -euo pipefail
trap "echo 'error: Script failed: see failed command above'" ERR

EXPORT_STATEMENTS="$(fib-arg-to-stat "$@")"
echo "$EXPORT_STATEMENTS"
eval "$EXPORT_STATEMENTS"
echo "FOO=${FOO}"
