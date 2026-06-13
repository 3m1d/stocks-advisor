#!/bin/bash
set -euo pipefail

# LSTM tickers served in Streamlit (LKOH, ROSN, T→TCSG). SBER/GAZP use CatBoost.
exec /app/docker/cron/run-job.sh stocks_dl.cli.dl_experiments \
  mode=retrain \
  environment=prod \
  experiment=lstm_checkpoint \
  'tickers=[LKOH,ROSN,TCSG]' \
  retrain.run_search=false \
  training.show_plots=false \
  training.verbose=true
