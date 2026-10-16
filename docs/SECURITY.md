# Security

## Principles

Least privilege, deny-by-default, no secrets in git.

## Remote collection

1. **TLS everywhere.** Prometheus `tls_config`, OTLP receiver `tls`, Loki push HTTPS.
   Self-signed is acceptable only with a private CA whose cert is deployed to scrapers;
   never use `insecure_skip_verify: true` in production.
2. **Auth.** Bearer token or basic auth on every scrape/push endpoint. Rotate every 90d.
   Example Prometheus scrape snippet is commented in `monitoring/prometheus.yml`.
3. **Restricted network.** Firewall scrape ports (9100, 8080) to the on-prem collector IPs only.
   Security-group / UFW example:
   `ufw allow from <collector-IP> to any port 9100 proto tcp`.
   Grafana (3000) is bound to localhost / VPN only — never public.
4. **Least privilege.** Dedicated `prometheus` / `promtail` users with read-only log/metric access.
   Cloud exporters use IAM roles / API tokens scoped to `cloudwatch:List*` + `Get*` (AWS)
   or read-only (DO), no write permissions.

## Secrets handling

- Runtime secrets via environment file or manager (e.g. `GRAFANA_ADMIN_PASSWORD`,
  scrape passwords, Slack webhook URL). `.gitignore` excludes `.env`, `*.pem/key/crt`.
- Change default `admin/admin` immediately; set `GF_USERS_ALLOW_SIGN_UP=false` (already in compose).
- Alertmanager webhook URLs with tokens go in an env-substituted file, not committed.

## Verification

```bash
./scripts/remote-check.sh                 # local stack + target UP check
REMOTE_HOST=node-01.example.internal ./scripts/remote-check.sh  # + remote TLS cert
```

Checklist before adding a remote target: DNS resolves, port reachable from collector,
valid cert (dates/CN), auth accepted (200 on `/metrics`), appears UP in Prometheus targets.
