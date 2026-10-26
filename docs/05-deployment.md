# Deployment

## Local

```bash
pip install -e .            # or: pip install -r requirements.txt
bep serve --port 8080       # http://127.0.0.1:8080
```

Data lands in `$BEP_DATA_DIR`, or `/data` when it exists and is writable, or
`~/.local/share/bep`. That directory holds `bep.sqlite3`, the uploaded IFC files and their
derived viewer payloads under `models/`.

## Fly.io

```bash
fly launch --no-deploy --copy-config          # the app name must be free on Fly
fly volumes create bep_data --size 1 --region nrt   # same region as primary_region
fly secrets set SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
fly deploy
```

The app is served openly unless a login is set; do that whenever the plans on it are not
demo data:

```bash
fly secrets set BEP_AUTH_USER=bep BEP_AUTH_PASSWORD=<password>
```

`fly.toml` mounts the volume at `/data`, health-checks `/healthz`, and suspends the machine
when idle (`auto_stop_machines = "suspend"`, `min_machines_running = 0`), so an occasional-use
instance costs close to nothing and wakes on the next request.

**Sizing.** The default is `shared-cpu-1x` with 1 GB, because IFC tessellation is the memory
peak, not request serving. A 200 MB IFC wants 2 GB. Size the volume for the models you expect
to keep, not just the database.

**Workers.** The container runs one gunicorn worker with eight threads. That is deliberate:
SQLite takes a single writer, and threads carry the concurrency an authoring tool actually
sees. To run more workers, move to Postgres with `DATABASE_URL` — the models are plain
SQLAlchemy and need no other change.

**AI in the cloud.** Ollama is not in the image. Either leave AI off — the panel reports that
no model is reachable and everything else works — or point it at a model endpoint you control:

```bash
fly secrets set BEP_CONFIG=/data/config.json
# then write /data/config.json with {"ai": {"base_url": "...", "model": "..."}}
```

Think before doing that: the prompt carries the plan's contents, and a BEP for a sensitive
asset should not leave your own infrastructure.

## RunPod

```bash
# on the pod
curl -fsSL https://raw.githubusercontent.com/mac999/bepbench/main/deploy/runpod.sh | bash
```

The script clones to `/workspace/bepbench`, installs into a virtualenv at
`/workspace/venv`, keeps the database and uploaded models in `/workspace/bep-data`, and
starts gunicorn on port 8080. Re-running it updates the code and restarts the service; it
refuses to touch a checkout with uncommitted changes.

It installs into a virtualenv rather than the system interpreter because Ubuntu 24.04
will not let pip replace distro packages — Flask needs a newer `blinker` than Debian ships,
and the Debian one has no `RECORD` file so pip cannot uninstall it. `--break-system-packages`
does not help.

**`/workspace` is only persistent if the pod has a network volume mounted there.** Without
one it is container disk: it survives a restart but not terminating the pod. The script
says so when it sees that, and `bep export <plan> --format json` is the way to take plans
out.

Expose port **8080** under *Expose HTTP Ports* when creating the pod — RunPod fixes the
HTTP port list at creation time, so adding one later means a new pod. If only the template's
default 8888 is exposed, `BEP_PORT=8888` serves on that instead, after stopping JupyterLab
(`pkill -f jupyter-lab`).

The pod's own SSH only accepts keys registered under **Settings → SSH Public Keys** before
the pod starts; the whole line including the `ssh-ed25519` prefix. The `ssh.runpod.io`
proxy route gives an interactive shell and ignores a command passed as an argument, so
scripted use needs the command on stdin.

**The proxy URL is public.** Anyone holding `https://<pod-id>-8080.proxy.runpod.net` can
reach the service, so by default the script generates a password and turns on basic
authentication. It is written once to `/workspace/bep-data/service.env` and reused on
redeploy. Read it with `grep BEP_AUTH_PASSWORD /workspace/bep-data/service.env`.

To serve openly — reasonable when the plans on that pod are throwaway — set
`BEP_NO_AUTH=1`. On a pod already running with a password it removes the stored
credentials, so a redeploy will not quietly put the login back:

```bash
curl -fsSL .../deploy/runpod.sh | BEP_NO_AUTH=1 bash
```

A pod restart starts the container fresh, so the service needs bringing back. The script
installs `/pre_start.sh`, the hook the pod template already runs, which detaches
`/workspace/bep-data/autostart.sh` and returns immediately — **that hook runs before sshd,
so anything slow in it delays SSH and can leave the pod unreachable.**

On port 8888 the helper also waits for the template to start JupyterLab, stops it, and
takes the port. Jupyter is started from `/start.sh` *after* the hook, so waiting for the
port up front would be racing a process that does not exist yet.

To bring it up by hand: `/workspace/bep-data/start.sh`. The log is
`/workspace/bep-data/autostart.log`.

## Any other host

The image is an ordinary Python web app:

```bash
docker build -t bepbench .
docker run -p 8080:8080 -v bep-data:/data -e SECRET_KEY=... bepbench
```

`libgomp1` is installed for ifcopenshell's geometry kernel; without it IFC upload fails and
everything else keeps working.

## Operations

| Task | Command |
| --- | --- |
| Health check | `GET /healthz` |
| Score every plan | `bep list` |
| Gate a submission in CI | `bep score <plan> --require-ready --fail-under 70` |
| Back up | Copy `$BEP_DATA_DIR`, or `bep export <plan> --format json` per plan |
| Check the effective settings | `bep config` |
| Check the model endpoint | `bep ai status` |
