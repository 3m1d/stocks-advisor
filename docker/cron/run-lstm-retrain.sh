#!/bin/bash
set -euo pipefail

exec /app/docker/cron/run-job.sh stocks_dl.cli.dl_experiments \
  mode=retrain \
  environment=prod \
  experiment=lstm_checkpoint \
  retrain.run_search=false \
  training.show_plots=false \
  training.verbose=true
