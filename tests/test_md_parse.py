import urllib.request
from app.storage import save_fmu, read_model_description

# Download sample FMU
path = "app/library/msl/BouncingBall.fmu"

# Parse
meta = read_model_description(path)
assert meta.modelName == "BouncingBall", "Wrong model name"
assert meta.fmiVersion in ["2.0", "3.0"], "Wrong FMI version"
assert len(meta.modelVariables) >= 1, "No variables parsed"
print("MD parse test passed")
