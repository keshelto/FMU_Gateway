# FMU Gateway Hybrid Architecture

## Overview
The FMU Gateway platform is split into three deliverables:
- **Open SDK**: Python package distributed publicly for engineers to integrate FMU execution into their workflows.
- **Private API**: Proprietary backend service that authenticates API-key requests, manages credits, and executes FMUs in an isolated environment.
- **Shared Specs**: Contractual interface definitions ensuring the SDK and backend evolve together without breaking changes.

## Component Boundaries
1. **open-sdk/** contains the public Python client that mirrors the OpenAPI specification. No proprietary execution logic or billing details are included.
2. **private-api/** implements the FastAPI backend, Stripe billing, and FMU sandbox runner. Source access is restricted.
3. **shared-specs/** provides the API contract, pricing tiers, and license for partners who need to integrate without accessing backend code.

## Deployment Targets
- **Docker Compose** for local integration testing.
- **AWS ECS** as the reference managed container environment for production.
- **Vercel** configuration for rapid preview deployments of the API.

## AWS Deployment Steps
1. Build and push the private API image to Amazon ECR using `make build` and `make deploy`.
2. Update `deploy/aws_ecs_config.json` with live subnet and security group IDs.
3. Use AWS CLI: `aws ecs update-service --cli-input-json file://deploy/aws_ecs_config.json` to roll out updates.
4. Configure AWS Secrets Manager with `STRIPE_KEY`, `JWT_SECRET`, and `S3_BUCKET_URL` environment variables.

## GCP Deployment Steps
1. Build the container: `gcloud builds submit --config cloudbuild.yaml` (create based on Dockerfile if needed).
2. Deploy to Cloud Run: `gcloud run deploy fmu-gateway-api --image gcr.io/PROJECT_ID/private-api:latest --platform managed`.
3. Set service environment variables: `gcloud run services update fmu-gateway-api --set-env-vars STRIPE_KEY=...`.
4. Configure Stripe webhook endpoint to the Cloud Run URL for billing events.

## Security Considerations
- All FMU executions happen inside Docker containers with restricted permissions.
- API keys are validated before execution and translated into JWT tokens for internal service communication.
- Billing events emit Stripe usage records and decrement internal credits atomically.
