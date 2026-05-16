#!/bin/bash
# =============================================================================
# MediFlow Pre-Submission Check
# Usage: bash scripts/pre_submit_check.sh [https://your-domain.com]
# =============================================================================

set -euo pipefail

DOMAIN="${1:-https://your-domain.com}"
FIXTURE="tests/fixtures/sample_xray_normal.png"
RESULT_FILE="/tmp/mediflow_analyze_result.json"
PASS=0
FAIL=0

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "🔍 MediFlow Pre-Submission Check"
echo "================================"
echo "   Target: $DOMAIN"
echo "   Date  : $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo ""

# ── Helper ────────────────────────────────────────────────────────────────────
check() {
  local name="$1"
  local result="$2"
  if [ "$result" = "ok" ]; then
    echo -e "  ${GREEN}✅ $name${NC}"
    PASS=$((PASS + 1))
  else
    echo -e "  ${RED}❌ $name — $result${NC}"
    FAIL=$((FAIL + 1))
  fi
}

warn() {
  echo -e "  ${YELLOW}⚠️  $1${NC}"
}

section() {
  echo ""
  echo "── $1 ──────────────────────────────────────────"
}

# ── 1. Local environment ──────────────────────────────────────────────────────
section "Local Environment"

# 1a. .env file exists
check ".env file present" \
  "$([ -f .env ] && echo ok || echo 'missing — copy .env.example and fill values')"

# 1b. Required env vars set (read from .env if present)
if [ -f .env ]; then
  # shellcheck disable=SC1091
  set -a; source .env 2>/dev/null || true; set +a
fi

for VAR in GEMINI_API_KEY SPEECHMATICS_API_KEY MEDIFLOW_ENCRYPTION_KEY DOMAIN; do
  VAL="${!VAR:-}"
  if [ -z "$VAL" ] || [[ "$VAL" == *"your_"* ]] || [[ "$VAL" == *"<"* ]]; then
    check "Env: $VAR" "not set or still placeholder"
  else
    check "Env: $VAR" "ok"
  fi
done

# 1c. .env not committed to git
if git -C . rev-parse --is-inside-work-tree &>/dev/null; then
  TRACKED=$(git ls-files .env 2>/dev/null)
  check ".env not tracked by git" \
    "$([ -z "$TRACKED" ] && echo ok || echo 'DANGER: .env is committed — remove it immediately')"
fi

# 1d. Fixture file exists
check "Test fixture present ($FIXTURE)" \
  "$([ -f "$FIXTURE" ] && echo ok || echo "missing — run: python tests/fixtures/generate_sample.py")"

# ── 2. Docker containers ──────────────────────────────────────────────────────
section "Docker Containers"

if command -v docker &>/dev/null && docker compose version &>/dev/null 2>&1; then
  for SVC in backend frontend nginx; do
    STATE=$(docker compose ps --format json 2>/dev/null \
      | python3 -c "
import sys, json
lines = sys.stdin.read().strip().splitlines()
for line in lines:
    try:
        d = json.loads(line)
        if '$SVC' in d.get('Service','') or '$SVC' in d.get('Name',''):
            print('ok' if d.get('State','') == 'running' else d.get('State','unknown'))
            sys.exit(0)
    except Exception:
        pass
print('not found')
" 2>/dev/null || echo "unknown")
    check "Container: $SVC running" "$STATE"
  done

  # Disk space — warn if < 1 GB free
  FREE_KB=$(df / | awk 'NR==2 {print $4}')
  FREE_GB=$(echo "scale=1; $FREE_KB / 1048576" | bc 2>/dev/null || echo "?")
  if [ "$FREE_KB" -lt 1048576 ] 2>/dev/null; then
    check "Disk space (>1 GB free)" "${FREE_GB}GB free — low, may cause OOM"
  else
    check "Disk space (>1 GB free)" "ok (${FREE_GB}GB)"
  fi
else
  warn "Docker not available locally — skipping container checks"
fi

# ── 3. API connectivity ───────────────────────────────────────────────────────
section "API Connectivity"

# Fetch health once, reuse for multiple checks
HEALTH_JSON=$(curl -sf --max-time 10 "$DOMAIN/api/health" 2>/dev/null || echo "{}")

# 3a. API health status
API_STATUS=$(echo "$HEALTH_JSON" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('ok' if d.get('status')=='ok' else 'fail')" \
  2>/dev/null || echo "unreachable")
check "API /api/health reachable" "$API_STATUS"

# 3b. Model loaded
MODEL_STATUS=$(echo "$HEALTH_JSON" | python3 -c \
  "import sys,json; d=json.load(sys.stdin); print('ok' if d.get('model_loaded') else 'not loaded')" \
  2>/dev/null || echo "unknown")
check "Model loaded" "$MODEL_STATUS"

# 3c. Queue not saturated
QUEUE_STATUS=$(echo "$HEALTH_JSON" | python3 -c \
  "import sys,json
d=json.load(sys.stdin)
depth=d.get('queue_depth',0)
cap=d.get('queue_capacity',5)
print('ok' if depth < cap else f'saturated ({depth}/{cap})')" \
  2>/dev/null || echo "unknown")
check "Inference queue available" "$QUEUE_STATUS"

# 3d. Frontend HTTP 200
FRONT_CODE=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 10 "$DOMAIN" 2>/dev/null || echo "000")
check "Frontend HTTP 200" \
  "$([ "$FRONT_CODE" = "200" ] && echo ok || echo "HTTP $FRONT_CODE")"

# 3e. SSL certificate valid (curl fails with non-zero exit if cert invalid)
SSL_CHECK=$(curl -sf --max-time 5 "$DOMAIN" -o /dev/null 2>&1 && echo ok || echo "SSL/TLS error")
check "SSL certificate valid" "$SSL_CHECK"

# 3f. POST /api/analyze reachable (no file — expect 422, not 000)
ANALYZE_CODE=$(curl -sf -o /dev/null -w "%{http_code}" --max-time 10 \
  -X POST "$DOMAIN/api/analyze" 2>/dev/null || echo "000")
check "POST /api/analyze reachable" \
  "$([ "$ANALYZE_CODE" != "000" ] && echo ok || echo "unreachable (connection refused)")"

# ── 4. Full analysis with fixture ─────────────────────────────────────────────
section "End-to-End Analysis"

if [ ! -f "$FIXTURE" ]; then
  warn "Skipping E2E checks — fixture missing"
else
  # 4a. Response time < 30s
  START_NS=$(date +%s%N 2>/dev/null || echo "0")
  HTTP_CODE=$(curl -sf -o "$RESULT_FILE" -w "%{http_code}" --max-time 35 \
    -X POST "$DOMAIN/api/analyze" \
    -F "xray_image=@${FIXTURE};type=image/png" \
    2>/dev/null || echo "000")
  END_NS=$(date +%s%N 2>/dev/null || echo "0")

  if [ "$START_NS" != "0" ] && [ "$END_NS" != "0" ]; then
    MS=$(( (END_NS - START_NS) / 1000000 ))
    check "Response time <30s (${MS}ms)" \
      "$([ "$MS" -lt 30000 ] && echo ok || echo "${MS}ms — exceeds 30s target")"
  else
    warn "Nanosecond timer unavailable — skipping timing check"
  fi

  # 4b. HTTP 200
  check "POST /api/analyze HTTP 200" \
    "$([ "$HTTP_CODE" = "200" ] && echo ok || echo "HTTP $HTTP_CODE")"

  if [ "$HTTP_CODE" = "200" ] && [ -f "$RESULT_FILE" ]; then
    # 4c. Heatmap present and valid data URL
    HM=$(python3 -c \
      "import json; d=json.load(open('$RESULT_FILE')); \
       v=d.get('heatmap_base64',''); \
       print('ok' if v.startswith('data:image/png;base64,') and len(v)>100 else 'missing or empty')" \
      2>/dev/null || echo "parse error")
    check "Grad-CAM heatmap_base64 present" "$HM"

    # 4d. Diagnosis field non-empty
    DIAG=$(python3 -c \
      "import json; d=json.load(open('$RESULT_FILE')); \
       print('ok' if d.get('diagnosis','').strip() else 'empty')" \
      2>/dev/null || echo "parse error")
    check "diagnosis field non-empty" "$DIAG"

    # 4e. Confidence in [0, 1]
    CONF=$(python3 -c \
      "import json; d=json.load(open('$RESULT_FILE')); \
       c=d.get('confidence',None); \
       print('ok' if isinstance(c,(int,float)) and 0<=c<=1 else f'invalid: {c}')" \
      2>/dev/null || echo "parse error")
    check "confidence in [0.0, 1.0]" "$CONF"

    # 4f. findings is a non-empty list
    FINDINGS=$(python3 -c \
      "import json; d=json.load(open('$RESULT_FILE')); \
       f=d.get('findings',[]); \
       print('ok' if isinstance(f,list) and len(f)>0 else 'empty or missing')" \
      2>/dev/null || echo "parse error")
    check "findings list non-empty" "$FINDINGS"

    # 4g. finance_estimate has required keys
    FIN=$(python3 -c \
      "import json; d=json.load(open('$RESULT_FILE')); \
       fe=d.get('finance_estimate',{}); \
       ok=all(k in fe for k in ['total_idr','bpjs_covered']); \
       print('ok' if ok else 'missing keys')" \
      2>/dev/null || echo "parse error")
    check "finance_estimate keys present" "$FIN"

    # 4h. processing_time_ms present
    PT=$(python3 -c \
      "import json; d=json.load(open('$RESULT_FILE')); \
       t=d.get('processing_time_ms'); \
       print('ok' if isinstance(t,(int,float)) else 'missing')" \
      2>/dev/null || echo "parse error")
    check "processing_time_ms present" "$PT"
  else
    warn "Skipping response body checks — analyze request did not return 200"
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────────────
TOTAL=$((PASS + FAIL))
echo ""
echo "================================"
echo "  Checks : $TOTAL"
echo -e "  Passed : ${GREEN}$PASS${NC}"
echo -e "  Failed : ${RED}$FAIL${NC}"
echo "================================"

if [ "$FAIL" -eq 0 ]; then
  echo -e "${GREEN}🎉 ALL CHECKS PASSED — READY TO SUBMIT!${NC}"
  exit 0
else
  echo -e "${RED}⚠️  Fix $FAIL issue(s) before submitting.${NC}"
  echo ""
  echo "Common fixes:"
  echo "  • Missing env vars  → cp .env.example .env && nano .env"
  echo "  • Container down    → docker compose up -d --build"
  echo "  • Model not loaded  → docker compose logs backend | tail -50"
  echo "  • SSL error         → docker compose logs certbot | tail -20"
  echo "  • Slow response     → docker compose exec backend python -c \\"
  echo "      \"from models.xray_analyzer import export_artefacts; export_artefacts()\""
  exit 1
fi
