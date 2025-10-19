# Dockerfile for testing the FMU Gateway SDK
FROM python:3.11-slim

WORKDIR /opt/fmu-gateway-sdk
COPY . .
RUN pip install --no-cache-dir -e .[test] || pip install --no-cache-dir -e .

CMD ["python", "examples/run_fmu.py"]
