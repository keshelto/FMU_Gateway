# FMU Library Management

This guide explains how to expand the built-in FMU library that the gateway exposes at the `/library` endpoint. By default the repository ships with a single Modelica Standard Library (MSL) example (`BouncingBall.fmu`). You can add more FMUs either by exporting them from OpenModelica or by placing pre-built FMUs in the library folder.

## Folder layout

Library FMUs are served from `app/library/msl`. Each `.fmu` file becomes available through the API with the identifier `msl:<file_stem>`. For example, the file `app/library/msl/BouncingBall.fmu` is addressed as `msl:BouncingBall` when calling `/simulate`.

```
app/
  library/
    msl/
      BouncingBall.fmu
      <add-your-model>.fmu
```

To publish a new FMU to the library, drop it in this directory and commit the file. The `/library` endpoint automatically reads the FMU metadata (model name, FMI version, GUID, description) on startup—no extra configuration is required.

## Option 1 – Export new FMUs from OpenModelica

1. Install OpenModelica locally and ensure the `OMPython` package is available in your Python environment.
2. Use the catalog exporter to discover and build FMUs directly from the Modelica Standard Library:
   ```bash
   # Preview the first 10 candidates inside Modelica.Mechanics (no FMUs written)
   python scripts/msl_catalog_exporter.py --packages Modelica.Mechanics --limit 10 --dry-run

   # Export all "Examples" models from Modelica.Blocks as FMI 3.0 ME/CS FMUs
   python scripts/msl_catalog_exporter.py \
       --packages Modelica.Blocks \
       --only-examples \
       --output ~/Downloads/msl_fmus
   ```
   The script will connect to your local OpenModelica installation, iterate over the
   selected packages, and emit FMUs into the requested output directory.
3. Copy the generated `.fmu` files into `app/library/msl/` (keep whichever flavour—ME, CS, or both—you need). The helper script
   `scripts/populate_fmu_library.py` can bulk-copy and validate a directory of FMUs for you.
4. Commit the new FMUs so they are available to all agents and deployments.

## Option 2 – Add existing FMUs manually

If you already have FMUs from suppliers or other tools, simply copy them into `app/library/msl/`. Use descriptive filenames because the stem becomes the public identifier. For example, a file named `TwoPhasePump_CS.fmu` will be reachable as `msl:TwoPhasePump_CS`.

You can speed this up with the helper script `scripts/populate_fmu_library.py` which copies one or more `.fmu` archives (or entire directories of FMUs) into the library and validates that the metadata can be read:

```bash
python scripts/populate_fmu_library.py path/to/fmus/*.fmu

# Example: copy everything from an export directory
python scripts/populate_fmu_library.py ~/Downloads/msl_fmus

# Add --dry-run to preview actions or --replace to overwrite existing files
python scripts/populate_fmu_library.py ~/Downloads/msl_fmus --dry-run
```

## Verifying the library

After adding FMUs you can confirm that the gateway can discover them by running the local server and querying `/library`:

```bash
uvicorn app.main:app --reload
curl -H "Authorization: Bearer <api-key>" http://localhost:8000/library
```

You should see the new entries with their metadata. If an FMU fails to load it will be skipped; check the server logs for validation errors.

## Distributing larger collections

For sizeable libraries consider storing the FMUs in object storage (e.g., S3) and syncing them into `app/library/msl/` during deployment. As long as the files are present on disk before the server starts, they will appear in the `/library` response and can be simulated with `fmu_id="msl:<file_stem>"`.
