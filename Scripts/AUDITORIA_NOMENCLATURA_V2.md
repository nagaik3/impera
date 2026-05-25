# Auditoria Nomenclatura v2.0 — Real-Time Webhook + Polling

## Overview

Nomenclatura validation now uses a hybrid approach:
- **Webhook (Real-time)**: Validates tasks immediately upon creation (port 5003)
- **Polling (Safety net)**: Checks all active tasks every 6 hours for missed issues

This reduces latency from 3 hours to **seconds** for new tasks, while maintaining comprehensive validation.

## Architecture

```
ClickUp Task Created
    ↓
  Webhook (port 5003)
    ↓
auditoria_nomenclatura.py validates task name
    ↓
  If issues found → Comment on task with @mention
    ↓
  Copywriter is notified in real-time
```

## Running

### Start Webhook Server
```bash
python3 ~/Scripts/auditoria_nomenclatura.py --server
```

The server:
- Listens on port 5003 (configurable via `NOMENCLATURA_WEBHOOK_PORT` env var)
- Handles `/webhook/nomenclatura` POST endpoint
- Validates task names and posts comments
- Auto-starts on reboot via crontab

### Run Polling Validation
```bash
python3 ~/Scripts/auditoria_nomenclatura.py       # Check all 95+ tasks
python3 ~/Scripts/auditoria_nomenclatura.py --dry # Dry-run (no posts)
```

Currently runs every 6 hours via crontab:
```
0 */6 * * * . ~/.impera_env && python3 ~/Scripts/auditoria_nomenclatura.py
```

## Setup

### 1. Environment Variables

Ensure these are set in `~/.zshrc`:
```bash
export CLICKUP_API_TOKEN="pk_XXXXX..."
export NOMENCLATURA_WEBHOOK_PORT=5003
```

### 2. Start Webhook Server

#### Option A: Manual (for testing)
```bash
python3 ~/Scripts/auditoria_nomenclatura.py --server
```

#### Option B: Auto-start (production)
Already configured in crontab:
```bash
@reboot bash ~/Scripts/start_nomenclatura_webhook.sh
```

### 3. Register Webhook in ClickUp

1. Go to ClickUp Settings → Integrations → Webhooks
2. Create new webhook:
   - **Event**: `taskCreated`
   - **URL**: `http://localhost:5003/webhook/nomenclatura`
   - **Authorization**: (leave empty or use token if supported)

3. Test the webhook:
   - Create a new task with bad nomenclature (e.g., `[INVALID][BR][OF01][FB][AD01][V1]`)
   - Server should validate and post comment within seconds

## Validation Rules

Tasks must follow this pattern:
```
[NICHO][MERCADO?][OFERTA][FONTE][AD##][V##]
```

**Nichos**: DA, DB, ED, EM, ME, MM, NE, PT, ZB  
**Mercados**: BR, EUA (required for MM, EM)  
**Fontes**: FB, GG, KW, MG, OB, TB, TT, YT, VTURB  

### Example Valid Names
- `[MM][BR][OF01][FB][AD01][V1]` ✅
- `[ED][OF05][FB][AD10-AD15][V1-V3]` ✅
- `[EM][BR][OF02][FB][C35][V13-V24]` ✅

### Common Issues Found
- Unknown nicho (e.g., `[VS]` instead of valid list)
- Missing market for EM/MM (e.g., `[EM][OF05]` without [BR] or [EUA])
- Missing traffic source
- Unbalanced brackets

## Monitoring

### Check if webhook server is running
```bash
curl http://localhost:5003/webhook/nomenclatura -X OPTIONS
# Should return 404 or similar (not connection refused)
```

### View webhook logs
```bash
tail -f ~/Scripts/logs/nomenclatura_webhook.log
```

### View polling audit logs
```bash
tail -f ~/Scripts/auditoria_nomenclatura.log
```

## Troubleshooting

### Webhook not validating new tasks

1. **Check if server is running**:
   ```bash
   lsof -i :5003  # Should show python3 listening
   ```

2. **Check ClickUp webhook registration**:
   - Go to ClickUp Settings → Integrations → Webhooks
   - Verify webhook URL is correct and active
   - Look for recent deliveries/failures

3. **Test webhook manually**:
   ```bash
   curl -X POST http://localhost:5003/webhook/nomenclatura \
     -H "Content-Type: application/json" \
     -d '{
       "event": "taskCreated",
       "task": {
         "id": "test123",
         "name": "[VS][BR][OF01][FB][AD01][V1]"
       }
     }'
   ```

4. **Restart server**:
   ```bash
   pkill -f "python3 auditoria_nomenclatura.py --server"
   bash ~/Scripts/start_nomenclatura_webhook.sh
   ```

### Polling not catching issues

1. Check that crontab is active:
   ```bash
   crontab -l | grep auditoria
   ```

2. View audit logs:
   ```bash
   tail ~/Scripts/auditoria_nomenclatura.log
   ```

3. Run manual audit to test:
   ```bash
   python3 ~/Scripts/auditoria_nomenclatura.py --dry
   ```

## Performance Impact

| Metric | Before | After |
|--------|--------|-------|
| New task validation | ~180 min (3h avg) | ~1 sec (webhook) |
| API calls per day | ~8 (polling only) | ~8 + webhook events |
| Copywriter notification | Delayed | Immediate |
| Catch-all polling | Every 3h | Every 6h |

## Related Automation

See also:
- [gate_finalizado](gate_finalizado.py) — nomenclature + Drive validation before traffic
- [bot_gpdr.py](bot_gpdr.py) — auto-fix common nomenclature issues

## Version History

- **v2.0** (2026-05-24): Added webhook for real-time validation, reduced polling to 6h
- **v1.0**: Polling-only validation every 3 hours
