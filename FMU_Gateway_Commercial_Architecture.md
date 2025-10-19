# FMU Gateway Commercial Architecture Plan

## 1. System Architecture
```mermaid
graph TD
    SDK[Public Gateway SDK / CLI]
    API[Public REST / gRPC Endpoint]
    PAY[Payments & Authentication]
    EXEC[Private Execution Service]
    REG[Private FMU Storage & Validation Registry]
    A2A[Optional Agent-to-Agent API]

    SDK -->|HTTPS + API Key| API
    API --> PAY
    API --> EXEC
    API --> REG
    PAY -->|JWT issuance / Billing| API
    EXEC --> REG
    A2A --> API
    A2A --> PAY
```

## 2. Component Responsibilities

### Open-Source / Public Components
- **Gateway SDK & CLI**
  - Client libraries (Python/TypeScript) for uploading FMUs, requesting executions, and retrieving results.
  - Example projects and integration guides.
  - Public protocol documentation (OpenAPI spec, gRPC proto files) and developer onboarding docs.
- **Sample FMUs & Tutorials**
  - Reference FMUs that demonstrate the API.
  - Tutorials demonstrating CI/CD integration and simulation workflows.
- **Community Tooling**
  - Local sandbox runner for offline testing using mock execution backend.
  - Plug-in interface definitions for community contributions.

### Proprietary / Closed Components
- **Execution Service**
  - Container orchestration logic to spin up secure FMU runtime environments (Docker/Kubernetes/Lambda).
  - Scheduler, load balancing, and runtime monitoring.
  - Usage metering tied to billing and credit consumption.
- **FMU Storage & Validation Registry**
  - Encrypted FMU storage with permissioned access.
  - Validation pipelines for verifying compatibility, security scans, and certification.
  - Model metadata management and analytics data store.
- **Payments & Authentication Layer**
  - Billing, subscription management, and credit ledger.
  - OAuth/JWT issuance, API key management, and audit logging.
- **A2A Transaction Hub (future)**
  - Mediation logic for agent-to-agent negotiation, smart contracts, and transaction settlement.

## 3. Monetization Logic

### Account Lifecycle
1. User signs up on FMU Gateway portal and verifies email.
2. Payment provider (Stripe or Paddle) creates customer record and attaches pricing tier.
3. Dashboard issues API key(s); keys signed with HMAC and stored encrypted.
4. Each API request validates API key and JWT session.
5. Execution requests deduct credits based on FMU runtime metrics (CPU time, memory, storage).
6. Usage aggregated per billing cycle; invoices auto-generated via Stripe/Paddle.

### Credit Consumption Model
- **Base cost** per execution depending on model size and runtime class.
- **Dynamic surcharge** for extended simulation time, premium models, or A2A interactions.
- **Bulk discounts** applied to Pro/Enterprise tiers.

### Pricing Tier Schema
```json
{
  "tiers": [
    {
      "name": "Free",
      "monthly_price_usd": 0,
      "included_credits": 1000,
      "overage_rate_per_credit_usd": 0.05,
      "features": [
        "Community support",
        "Access to public FMU registry",
        "Basic analytics (7-day history)"
      ]
    },
    {
      "name": "Pro",
      "monthly_price_usd": 249,
      "included_credits": 150000,
      "overage_rate_per_credit_usd": 0.015,
      "features": [
        "Priority support",
        "Private FMU uploads",
        "Advanced analytics (90-day history)",
        "A2A API access (limited)"
      ]
    },
    {
      "name": "Enterprise",
      "monthly_price_usd": "custom",
      "included_credits": "custom",
      "overage_rate_per_credit_usd": "negotiated",
      "features": [
        "Dedicated account manager",
        "Custom SLA & on-prem options",
        "Unlimited team members",
        "Marketplace revenue share adjustments",
        "Full A2A API access"
      ]
    }
  ]
}
```

## 4. Security & Ring-Fencing
- **Authentication**: Mandatory API key header plus short-lived JWT issued by Payments & Auth service. JWT includes tier, credit balance, and scopes.
- **Execution Isolation**: FMUs run in private Docker images stored in private container registry or AWS Lambda functions with strict IAM roles. No direct code execution on public infrastructure.
- **Network Segmentation**: Execution Service resides in private VPC subnet, accessible only via API gateway.
- **Access Controls**: FMU Registry requires scoped JWT permissions. Audit trail for every FMU upload/download.
- **Source-Available License**: Add `LICENSE_COMMERCIAL` with “FMU Gateway Source-Available, Non-Commercial License” restricting commercial use of public components and clarifying proprietary backend code remains closed.
- **Rate Limiting & Abuse Detection**: Throttle API requests per tier; anomaly detection triggers manual review.

## 5. Data & IP Protection
- **Secure Storage**: Store FMUs in private S3 buckets (or GCS) with server-side encryption (SSE-KMS) and signed URL access that expires within minutes.
- **Checksum Verification**: Generate SHA-256 checksums upon upload. Certified FMUs require checksum match and pass static/dynamic validation suite.
- **Validation Pipeline**: Sandbox executes FMU with test vectors; results hashed and compared to expected tolerance to earn “Certified” badge.
- **Trademark Policy**: Provide guidelines: only certified partners can use “FMU Gateway Certified” mark, must follow brand assets guide, and include attribution statement.
- **Data Retention**: Define retention schedules for FMU logs, simulation outputs, and user data; allow enterprise customers to request purge.

## 6. Deployment Plan

### Containerization & Infrastructure
- Build Docker images for Execution Service, API Gateway, Payments/Auth service, and Registry service.
- Push images to private registry (ECR/Artifact Registry).
- Deploy via:
  - **AWS ECS Fargate**: Task definitions per service, ALB routing.
  - **GCP Cloud Run**: Managed serverless containers for API/Payments, with VPC connector to private registry.
  - **Vercel Edge Functions**: Optional for SDK proxy endpoints or docs hosting.

### Deployment Steps (AWS ECS example)
1. Provision VPC with public subnets (ALB) and private subnets (services, databases).
2. Create RDS (PostgreSQL) for metadata/billing linkage and Redis for job queue.
3. Configure S3 buckets with KMS encryption and IAM roles.
4. Set up ECS clusters, register services (API, Execution, Registry, Auth).
5. Configure CI/CD pipeline (GitHub Actions) to build, test, and deploy images.
6. Integrate Stripe/Paddle webhooks to update credit balances and trigger invoices.
7. Monitor with CloudWatch dashboards and alerts.

### SDK Interaction Flow
1. SDK obtains API key from user config (`~/.fmu_gateway/config`).
2. SDK authenticates via `/auth/token` to receive JWT.
3. Upload FMU via `/fmu/upload` (signed URL exchange).
4. Trigger execution via `/fmu/execute` with parameters; poll `/fmu/status/{job_id}`.
5. Download results via signed URL from `/fmu/results/{job_id}`.

### Environment Configuration Template
```env
# Public SDK config
FMUGW_BASE_URL="https://api.fmu-gateway.com"
FMUGW_API_KEY="<user-api-key>"

# Private services
DATABASE_URL="postgresql://user:pass@db.fmu.internal:5432/fmu_gateway"
REDIS_URL="redis://cache.fmu.internal:6379/0"
STRIPE_SECRET_KEY="sk_live_..."
PADDLE_VENDOR_ID="..."
JWT_SECRET="<32-byte-random>"
S3_BUCKET="fmu-gateway-private"
S3_REGION="us-east-1"
EXECUTION_IMAGE="private.ecr.aws/fmu/executor:latest"
FMU_VALIDATION_QUEUE="fmu-validation"
CLOUD_LOGGING_LEVEL="INFO"
```

## 7. Optional Extensions

### Plug-in Marketplace
- Curate marketplace where third-party developers list FMUs or extensions.
- Implement revenue-sharing model (e.g., 70/30 split) with automated payouts via Stripe Connect or Paddle Vendor.
- Marketplace approval workflow to ensure compliance with certification and licensing.
- Provide analytics to vendors (downloads, ratings, revenue).

### Analytics Dashboard
- Web dashboard for customers to view execution history, credit consumption, costs, and performance metrics.
- Integrate with data warehouse (BigQuery/Redshift) and visualization (Metabase/Looker Studio).
- Include anomaly detection alerts, export to CSV/JSON, and programmatic access via `/analytics` API.

## Appendix: Licensing & Compliance Actions
- Publish new license file `FMU Gateway Source-Available, Non-Commercial License` alongside existing open components.
- Update README to clarify open-core model, usage restrictions, and path to commercial tiers.
- Document data protection impact assessment (DPIA) and compliance posture (GDPR, SOC 2 roadmap).
