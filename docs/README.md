# LolixCopilot Documentation Index

Welcome to the technical and operational documentation for LolixCopilot, Golixco's AI-assisted video-editing workstation developed for the Meta Global AI Developer Hackathon.

## Document Directory

### 1. Product and Architecture
- [Product Architecture Specification](ARCHITECTURE.md): End-to-end system design, client-server data flow, S3 storage contracts, Lambda serverless media worker, and Supabase integration.
- [Product Specification](PRODUCT_SPEC.md): Core user workflows, target personas, non-linear editor design requirements, and feature scope.
- [Frontend Design System](FRONTEND_DESIGN_SYSTEM.md): Dark studio design tokens, typography, visual hierarchy, SMPTE timecode standards, and responsive viewport specifications.

### 2. Getting Started and Operations
- [Getting Started Guide](GETTING_STARTED.md): Step-by-step local development setup, environment configuration, dependency installation, and local service execution.
- [AWS Production Deployment](DEPLOYMENT_AWS.md): Complete architecture of the live deployment in AWS Region ap-south-1 (Mumbai), including EC2 host sizing, Nginx reverse proxy, CloudFront HTTPS edge front door, AWS Secrets Manager integration, S3 private media bucket, and Lambda media processor.
- [Troubleshooting Guide](TROUBLESHOOTING.md): Operational debugging procedures, common error resolutions, service health checks, and recovery workflows.

### 3. AI Intelligence and Inference Routing
- [AI Director Guide](AI_DIRECTOR.md): Natural-language conversational editing, visual scene breakdown, timestamped recommendation generation, and timeline operation execution.
- [AI Providers Specification](AI_PROVIDERS.md): Detailed integration analysis of Meta Model API (Muse Spark 1.3), Modal (Muse Glimmer 30B on NVIDIA H100), and Baseten (Muse Spark Open 1026).
- [Inference Routing & Auto Mode](INFERENCE_ROUTING.md): Orchestrator decision logic, multi-provider pipeline execution, fallback mechanisms, and structured EditingBlueprint schema validation.
- [Models Reference](MODELS.md): Inventory of configured models, parameter sizes, context windows, modalities, and execution environments.

### 4. Machine Learning and Fine-Tuning
- [Fine-Tuning & Adaptation Report](FINETUNING.md): Rigorous technical report on the Muse Glimmer 30B QLoRA fine-tuning pipeline on Modal H100 GPU compute, dataset construction, training trajectory, loss reduction analysis, and honest evaluation distinctions.
- [Datasets and Licences](DATASETS_AND_LICENSES.md): Provenance, structural schemas, and licensing terms for synthetic fixture datasets, reference benchmarks, and open-weight model weights.
- [Modal Architecture & Training Spec](MODAL_CREDIT_AND_TRAINING_SPEC.md): Breakdown of Modal CPU media processing and GPU fine-tuning costs under a 100 USD credit budget.

### 5. Security and Compliance
- [Security Architecture](SECURITY.md): Multi-tenant isolation via Supabase Row-Level Security, private S3 storage with presigned URLs, AWS Secrets Manager credential retrieval via IAM instance roles, and strict CORS policies.
- [Privacy Policy & Data Retention](PRIVACY.md): Data minimization principles, automatic 7-day storage lifecycle expiration, user media rights, and zero-training policies on private footage.

### 6. Presentation and Demonstration
- [Technical Presentation Brief](TECHNICAL_PRESENTATION_BRIEF.md): Comprehensive oral presentation briefing for hackathon judges, technical interviewers, and evaluators.
- [YouTube Demonstration Script](YOUTUBE_DEMO_SCRIPT.md): Step-by-step 2 to 4 minute video walkthrough script covering the verified 10-step creator demonstration.
- [Implementation Status](IMPLEMENTATION_STATUS.md): Current build state, test verification records, and deployment metadata.
