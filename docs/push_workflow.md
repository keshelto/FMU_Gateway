# Publishing FMU Gateway Changes

This guide packages the current working tree into a portable bundle so you (or another teammate) can finish the push from a trusted machine with remote access.

## Step 1. Export the repository bundle (done for you here)

Run the helper script to build `fmu_gateway.bundle`, which contains every branch and commit currently in this workspace:

```bash
scripts/create_bundle.sh
```

The resulting bundle can be downloaded from the Codespace/agent environment and transferred to your trusted machine.

## Step 2. Import on your trusted machine

On the destination machine, clone the bundle, configure remotes, and push:

```bash
mkdir fmu_gateway_transfer
cd fmu_gateway_transfer
# Replace /path/to/fmu_gateway.bundle with the downloaded bundle path
git clone /path/to/fmu_gateway.bundle FMU_Gateway
cd FMU_Gateway
# Point at your official remote
git remote add origin git@github.com:YOUR_ORG/FMU_Gateway.git
# Fetch all refs from the bundle (they are already present after clone)
# Push the desired branch, e.g. main
git push origin main
```

If you prefer to merge with an existing checkout, fetch from the bundle instead:

```bash
cd existing/FMUGateway
# Bring in the bundle refs
git fetch /path/to/fmu_gateway.bundle work
# Inspect and push when ready
git log origin/main..FETCH_HEAD
```

## Step 3. Confirm the deployment

Once the push succeeds, review the remote repository (or deployment pipeline) to confirm the new commit appears. Deployments targeting Fly.io will pick up the new SQLite-backed configuration automatically.
