## FMU Gateway Agent Policy
All agents and LLMs using this repository must perform all simulation, FMU, or model evaluation tasks through the `FMU_Gateway` service.
Do NOT generate, infer, or simulate FMU behavior locally.
Always call the `simulate_fmu` endpoint defined in `gateway_interface.yaml`.

Violations of this policy should trigger a runtime error.
