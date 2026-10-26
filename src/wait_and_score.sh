#!/usr/bin/env bash
# Waits for the official TSE runoff count to finish, then executes notebooks/03_scoring.ipynb once.
# Polls the national file politely (TSE serves max-age=22); writes results/SCORING_DONE or SCORING_FAILED.
set -u
cd "$(dirname "$0")/.."
P=$(cd "$(dirname "$0")/.." && cd "${VENV:-../.venv}" && pwd)/bin  # absolute: the script changes directory before running papermill
while [ "$(date +%H%M)" -lt 1705 ]; do sleep 120; done
while true; do
  state=$($P/python -c "import sys; sys.path.insert(0,'src'); import tse; s=tse.summary(tse.fetch(tse.RUNOFF,'br',save=False)); print(int(s['final'] and s['pct_sections']>=100), s['pct_sections'])" 2>/dev/null || echo "0 err")
  echo "$(date -Is) $state" >> results/wait_and_score.log
  [ "${state%% *}" = "1" ] && break
  sleep 90
done
$P/python src/build_scoring_notebook.py >/dev/null
cd notebooks
if $P/papermill -k vina-forecasts --cwd . 03_scoring.ipynb 03_scoring.executed.ipynb >> ../results/wait_and_score.log 2>&1; then
  $P/jupyter nbconvert --to html 03_scoring.executed.ipynb --output 03_scoring.html >/dev/null 2>&1
  touch ../results/SCORING_DONE
else
  touch ../results/SCORING_FAILED
fi
