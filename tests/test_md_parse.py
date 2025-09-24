import urllib.request
from app.storage import save_fmu, read_model_description

# Download sample FMU
url = "https://github.com/modelon-community/fmpy/raw/develop/tests/fmu/BouncingBall.fmu"
with urllib.request.urlopen(url) as response:
    content = response.read()
fmu_id, path = save_fmu(content)

# Parse
meta = read_model_description(path)
assert meta.modelName == "BouncingBall", "Wrong model name"
assert meta.fmiVersion in ["2.0", "3.0"], "Wrong FMI version"
assert len(meta.modelVariables) >= 1, "No variables parsed"
print("MD parse test passed")
