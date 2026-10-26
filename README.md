# Hermes Agent on Render
This repo runs Hermes Agent on Render's free Docker tier. It keeps the official image, adds a tiny health server, and keeps state in env vars.

```text
Render -> health port -> start.sh -> /opt/hermes/docker/entrypoint-dispatch.sh -> gateway run
```

## Deploy
1. Import the Render blueprint.
2. Set the four secret env vars in the Render dashboard.
3. Deploy the service.

## Free tier reality check
- Render free web services spin down after about 15 minutes; use UptimeRobot to ping the service URL every 5-10 minutes.
- Free workspaces share 750 instance-hours/month.
- The free tier gives 512 MB RAM; heavy browser automation may OOM.
- State is wiped on restart because there is no persistent disk.

## Risks
The health-server + exec wrapper is small glue around the official image. If the official image ever moves `entrypoint-dispatch.sh`, point the ENTRYPOINT back to `/init` or run the official image directly.

## Troubleshooting
| Problem | Likely cause | Fix |
| --- | --- | --- |
| No open ports / restart loop | No port bound on `$PORT` | Keep the health server running before `exec` |
| OOM | 512 MB free-tier limit | Reduce concurrency and disable heavy automation |
| Bot silent | Missing secrets or allowlist | Check Telegram token, allowed users, and OpenRouter key |

This setup is intentionally minimal and uses environment variables for all state that must survive a restart.
