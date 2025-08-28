import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import Settings,get_settings

settings = get_settings()

JARGON_DATABASE = {
    "NR": "Not recommended",
    "PF": "Personalized feed",
    "GH": "Geo-handler; a module responsible for routing features based on user region",
    "CDS": "Compliance Detection System",
    "DRT": "Data retention threshold; duration for which logs can be stored",
    "LCP": "Local compliance policy",
    "REDLINE": "Flag for legal review",
    "SOFTBLOCK": "A user-level limitation applied silently without notifications",
    "SPANNER": "A synthetic name for a rule engine",
    "SHADOWMODE": "Deploy feature in non-user-impact way to collect analytics only",
    "T5": "Tier 5 sensitivity data; more critical than T1-T4 in this internal taxonomy",
    "ASL": "Age-sensitive logic",
    "GLOW": "A compliance-flagging status, internally used to indicate geo-based alerts",
    "NSP": "Non-shareable policy (content should not be shared externally)",
    "JELLYBEAN": "Feature name for internal parental control system",
    "ECHOTRACE": "Log tracing mode to verify compliance routing",
    "BB": "Baseline Behavior; standard user behavior used for anomaly detection",
    "SNOWCAP": "A synthetic codename for the child safety policy framework",
    "FR": "Feature rollout status",
    "IMT": "Internal monitoring trigger",
    "COPPA": "Children's Online Privacy Protection Act",
    "GDPR": "General Data Protection Regulation",

    # --- Additional 100 test entries ---
    "API_GATEWAY": "Manages and routes API requests between clients and microservices",
    "RATE_LIMIT": "Mechanism to control number of requests per time window",
    "OAUTH2": "Industry-standard protocol for authorization",
    "JWT": "JSON Web Token used for secure user authentication",
    "RBAC": "Role-Based Access Control system",
    "ABAC": "Attribute-Based Access Control system",
    "SAML": "Security Assertion Markup Language for SSO",
    "SSO": "Single Sign-On, one login across multiple apps",
    "MFA": "Multi-Factor Authentication",
    "KYC": "Know Your Customer compliance process",
    "AML": "Anti-Money Laundering compliance process",
    "PII": "Personally Identifiable Information",
    "PHI": "Protected Health Information",
    "HIPAA": "Health Insurance Portability and Accountability Act",
    "SOC2": "Service Organization Control 2 certification",
    "ISO27001": "International security management certification",
    "TLS": "Transport Layer Security for encrypted communication",
    "SSL": "Secure Sockets Layer (legacy encryption protocol)",
    "HTTPS": "Secure HTTP protocol",
    "DNSSEC": "Domain Name System Security Extensions",
    "DDOS": "Distributed Denial of Service attack",
    "IDS": "Intrusion Detection System",
    "IPS": "Intrusion Prevention System",
    "WAF": "Web Application Firewall",
    "SIEM": "Security Information and Event Management",
    "SOAR": "Security Orchestration, Automation, and Response",
    "EPP": "Endpoint Protection Platform",
    "EDR": "Endpoint Detection and Response",
    "XDR": "Extended Detection and Response",
    "CASB": "Cloud Access Security Broker",
    "SASE": "Secure Access Service Edge",
    "ZTNA": "Zero Trust Network Access",
    "IAM": "Identity and Access Management",
    "PKI": "Public Key Infrastructure",
    "HSM": "Hardware Security Module",
    "SAST": "Static Application Security Testing",
    "DAST": "Dynamic Application Security Testing",
    "IAST": "Interactive Application Security Testing",
    "RASP": "Runtime Application Self-Protection",
    "CSPM": "Cloud Security Posture Management",
    "CNAPP": "Cloud-Native Application Protection Platform",
    "CWPP": "Cloud Workload Protection Platform",
    "CI/CD": "Continuous Integration and Continuous Deployment",
    "DEVOPS": "Practices that unify software development and operations",
    "MLOPS": "Machine Learning Operations",
    "AIOPS": "AI for IT Operations",
    "OBSERVABILITY": "Ability to measure system state from outputs",
    "LOG_AGGREGATOR": "Central system for collecting application logs",
    "TRACING": "Tracking requests across distributed systems",
    "METRICS": "Quantitative system health data",
    "ALERTING": "Notification system for abnormal events",
    "DASHBOARD": "Visual representation of system metrics",
    "HEALTHCHECK": "Endpoint to verify service status",
    "LOAD_BALANCER": "Distributes traffic across multiple servers",
    "FAILOVER": "Automatic switching to backup on failure",
    "HA": "High Availability design principle",
    "DR": "Disaster Recovery plan",
    "BACKUP_POLICY": "Schedule and rules for data backup",
    "REPLICATION": "Duplicating data across systems",
    "SHARDING": "Splitting data across multiple databases",
    "CACHE": "Temporary data store for performance",
    "CDN": "Content Delivery Network for global distribution",
    "QUEUE": "Message queue for asynchronous processing",
    "PUBSUB": "Publish-subscribe messaging system",
    "EVENT_BUS": "Central communication system for events",
    "MICROSERVICE": "Small, independently deployable service",
    "MONOLITH": "Single unified codebase architecture",
    "CONTAINER": "Lightweight isolated runtime environment",
    "DOCKER": "Platform for building and running containers",
    "KUBERNETES": "Orchestration system for containers",
    "HELM": "Package manager for Kubernetes",
    "SERVICE_MESH": "Manages service-to-service communication",
    "ETCD": "Distributed key-value store for configs",
    "CONSUL": "Service discovery and config tool",
    "NOMAD": "Workload scheduler by HashiCorp",
    "VAULT": "Secrets management system by HashiCorp",
    "TERRAFORM": "Infrastructure as Code tool",
    "ANSIBLE": "Automation tool for configuration management",
    "CHEF": "Infrastructure automation tool",
    "PUPPET": "Configuration management system",
    "CLOUDFORMATION": "AWS Infrastructure as Code service",
    "ARM_TEMPLATES": "Azure Resource Manager templates",
    "BICEP": "DSL for Azure Infrastructure as Code",
    "GCP_DEPLOYMENT_MANAGER": "Google Cloud infra management tool",
    "SPOT_INSTANCE": "EC2 instance priced via unused capacity",
    "ON_DEMAND_INSTANCE": "EC2 instance billed hourly",
    "RESERVED_INSTANCE": "Discounted EC2 with time commitment",
    "EKS": "Elastic Kubernetes Service",
    "AKS": "Azure Kubernetes Service",
    "GKE": "Google Kubernetes Engine",
    "LAMBDA": "AWS serverless function service",
    "CLOUD_FUNCTIONS": "Google Cloud Functions",
    "AZURE_FUNCTIONS": "Microsoft Azure Functions",
    "SERVERLESS": "Compute model without managing servers",
    "FARGATE": "Serverless compute for containers on AWS",
    "APPCONFIG": "Centralized configuration system",
    "SECRETS_MANAGER": "Cloud service for secret storage",
    "PARAMETER_STORE": "AWS Systems Manager key-value store",
    "CLOUDWATCH": "AWS monitoring and observability service",
    "STACKDRIVER": "Google Cloud monitoring/logging",
    "APPINSIGHTS": "Azure Application Insights monitoring",
    "NEWRELIC": "Application performance monitoring tool",
    "DATADOG": "Monitoring and security platform",
    "PROMETHEUS": "Open-source monitoring system",
    "GRAFANA": "Visualization and dashboarding tool",
}

MONGO_URI = "Insert Mongo URL here (fix)"
DB_NAME = "Insert DB name here (fix)"

async def insert_jargon():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db["jargon_terms"]

    # Convert dict into list of documents
    documents = [{"term": k, "definition": v} for k, v in JARGON_DATABASE.items()]

    # Insert many
    result =  collection.insert_many(documents)
    print(f"Inserted {len(result.inserted_ids)} jargon terms!")

    await client.close()

if __name__ == "__main__":
    asyncio.run(insert_jargon())