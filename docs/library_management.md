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
2. Edit `scripts/export_msl_fmus.py` and extend the `models` list with the fully-qualified Modelica class names you want to export.
3. Run the exporter:
   ```bash
   python scripts/export_msl_fmus.py
   ```
   The script generates FMI 3.0 Model Exchange and Co-Simulation FMUs in the `msl_fmus/` folder.
4. Copy the generated `.fmu` files into `app/library/msl/` (keep whichever flavour—ME, CS, or both—you need).
5. Commit the new FMUs so they are available to all agents and deployments.

## Option 2 – Add existing FMUs manually

If you already have FMUs from suppliers or other tools, simply copy them into `app/library/msl/`. Use descriptive filenames because the stem becomes the public identifier. For example, a file named `TwoPhasePump_CS.fmu` will be reachable as `msl:TwoPhasePump_CS`.

## Verifying the library

After adding FMUs you can confirm that the gateway can discover them by running the local server and querying `/library`:

```bash
uvicorn app.main:app --reload
curl -H "Authorization: Bearer <api-key>" http://localhost:8000/library
```

You should see the new entries with their metadata. If an FMU fails to load it will be skipped; check the server logs for validation errors.

## Distributing larger collections

For sizeable libraries consider storing the FMUs in object storage (e.g., S3) and syncing them into `app/library/msl/` during deployment. As long as the files are present on disk before the server starts, they will appear in the `/library` response and can be simulated with `fmu_id="msl:<file_stem>"`.
