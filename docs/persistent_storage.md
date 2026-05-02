# Persistent Hosted Storage

The web app can use a mounted filesystem directory for browser-created runs,
draft scenarios, telemetry layouts, report metadata, and gallery metadata. This
keeps generated JSON state alive across redeploys without adding a paid database
or object-storage dependency.

## Storage Root

By default, the storage helper uses the existing local browser output directory:

```text
outputs/web_runs
```

Set `AEROSIM_STORAGE_DIR` to move that root to a persistent mount:

```bash
AEROSIM_STORAGE_DIR=/var/data/aerosim-storage
```

The helper exposes five safe namespaces under that root:

```text
runs/
drafts/
layouts/
reports/
gallery/
```

Each JSON object is addressed by a validated id or slug and written as
`<id>.json`. Ids cannot contain slashes, `..`, or path traversal segments.

## Render Setup

For Render, create a Persistent Disk on the web service and mount it at a stable
path such as:

```text
/var/data/aerosim-storage
```

Then add an environment variable on the same Render service:

```text
AEROSIM_STORAGE_DIR=/var/data/aerosim-storage
```

If you prefer to keep generated browser runs under the existing output shape,
mount the disk at `/app/outputs` and set:

```text
AEROSIM_STORAGE_DIR=/app/outputs/web_runs
```

The storage helper writes `.aerosim_storage_manifest.json` in the selected root.
The manifest records the storage schema version, safe namespaces, and whether the
root came from `AEROSIM_STORAGE_DIR`. Route code can also call
`storage_status()` to report whether storage is env-backed and writable.

## Limitations

- This is file-backed storage for one service instance, not a shared database.
- Atomic JSON writes use a temporary file and replace within the same directory;
  they assume the storage root is on one filesystem.
- Render disks are tied to the service and region. Backups, exports, and
  cross-service sharing need separate operational handling.
- Do not store secrets here. Treat public run metadata and shared drafts as
  application data.
- This foundation does not change API routes by itself. Route integration should
  import `get_storage()`, `get_storage_root()`, or `storage_status()` and map API
  resources into the safe namespaces.

