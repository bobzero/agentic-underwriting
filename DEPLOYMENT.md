# Agentic Underwriting Deployment Guide

## Overview

This guide provides step-by-step instructions for deploying the Agentic Underwriting application to Azure with security best practices.

## Architecture

- **Backend**: Python FastAPI running on Azure App Service (Linux)
- **Frontend**: Next.js application running on Azure App Service (Linux)
- **Storage**: Azure Storage Account with identity-based access (no SAS keys)
- **Secrets**: Azure Key Vault for sensitive configuration
- **Monitoring**: Application Insights + Log Analytics

## Prerequisites

1. Azure subscription with access to create resources in `rg-agentic-underwriting`
2. Azure CLI installed and authenticated (`az login --use-device-code`)
3. Python 3.11+
4. Node.js 20+
5. `zip` utility installed

## Security Features

✓ **Identity-Based Access**: Uses managed identities instead of connection strings/SAS keys
✓ **HTTPS Only**: All App Services enforce TLS 1.2+
✓ **No Public Blob Access**: Storage account doesn't allow public blob access
✓ **Key Vault Integration**: Secrets are stored in Azure Key Vault
✓ **RBAC**: Fine-grained role-based access control (Blob Data Contributor/Reader)
✓ **Logging**: All activities logged to Log Analytics workspace

## Deployment Steps

### Option 1: Automated Deployment (Recommended)

```bash
# Make the deployment script executable
chmod +x deploy.sh

# Run the deployment
./deploy.sh

# Show available overrides and current defaults
./deploy.sh --help

# Example override
./deploy.sh --location eastus --environment demo
```

Current script defaults:
1. Resource group: `rg-agentic-underwriting`
2. Location: `northcentralus`
3. Environment: `demo-ron`
4. App name: `agentic-underwriting`

The script will:
1. Validate prerequisites
2. Create/verify the resource group
3. Deploy infrastructure (Bicep)
4. Build and deploy backend
5. Build and deploy frontend
6. Configure application settings
7. Display deployment summary

Important configuration note:
1. Updating `agentic-underwriting-backend/.env` in the repository does not automatically update Azure App Service settings.
2. Runtime config for deployed apps comes from App Service Application Settings (or Key Vault references).
3. You can apply new settings without a full redeploy by running `az webapp config appsettings set`.

### Option 2: Manual Deployment

#### Step 1: Deploy Infrastructure

```bash
az deployment group create \
  --resource-group rg-agentic-underwriting \
  --template-file infra/main.bicep \
  --parameters location=northcentralus environment=demo-ron appName=agentic-underwriting
```

#### Step 2: Deploy Backend

```bash
cd agentic-underwriting-backend
zip -r ../backend.zip . -x "*.git*" "__pycache__*" "*.pyc" ".env" ".venv*"
cd ..

az webapp deployment source config-zip \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-demo-ron \
  --src backend.zip
```

#### Step 3: Deploy Frontend

```bash
cd agentic-underwriting-ui
npm ci
npm run build
zip -r ../frontend.zip . -x "*.git*" "node_modules*" ".next*" ".env*"
cd ..

az webapp deployment source config-zip \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-frontend-demo-ron \
  --src frontend.zip
```

## Post-Deployment Configuration

### 1. Configure LLM Provider (if using Azure OpenAI)

```bash
az webapp config appsettings set \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-demo-ron \
  --settings \
    AZURE_OPENAI_ENDPOINT="https://<your-resource>.openai.azure.com/" \
    AZURE_OPENAI_DEPLOYMENT="<deployment-name>"
```

For API keys, store in Key Vault:

```bash
az keyvault secret set \
  --vault-name <key-vault-name> \
  --name "AZURE-OPENAI-API-KEY" \
  --value "<api-key>"
```

Then reference in App Service:

```bash
az webapp config appsettings set \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-demo-ron \
  --settings "AZURE_OPENAI_API_KEY=@Microsoft.KeyVault(SecretUri=https://<vault-name>.vault.azure.net/secrets/AZURE-OPENAI-API-KEY/)"
```

### 2. Configure CORS

Update CORS settings if frontend and backend are at different URLs:

```bash
az webapp config appsettings set \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-demo-ron \
  --settings \
    "CORS_ORIGINS=https://<your-frontend-url>"
```

### 3. Configure Telemetry (Optional)

```bash
az webapp config appsettings set \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-demo-ron \
  --settings \
    "APPLICATIONINSIGHTS_CONNECTION_STRING=<connection-string>" \
    "OTEL_SERVICE_NAME=agentic-underwriting-backend"
```

### 4. Configure Additional Agents (Optional)

If using Foundry agents or location intelligence:

```bash
az keyvault secret set --vault-name <kv-name> --name "FOUNDRY-FABRIC-AGENT-ENDPOINT" --value "<endpoint>"
az keyvault secret set --vault-name <kv-name> --name "FOUNDRY-FABRIC-AGENT-NAME" --value "<agent-name>"
```

Reference in App Service:

```bash
az webapp config appsettings set \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-demo-ron \
  --settings \
    "FOUNDRY_FABRIC_AGENT_ENDPOINT=@Microsoft.KeyVault(SecretUri=https://<vault-name>.vault.azure.net/secrets/FOUNDRY-FABRIC-AGENT-ENDPOINT/)" \
    "FOUNDRY_FABRIC_AGENT_NAME=@Microsoft.KeyVault(SecretUri=https://<vault-name>.vault.azure.net/secrets/FOUNDRY-FABRIC-AGENT-NAME/)"
```

## Accessing the Application

After deployment, access your application at the Frontend URL shown in the deployment output:

```
https://agentic-underwriting-frontend-demo-ron.azurewebsites.net
```

## Scaling Considerations

### Vertical Scaling (Increase Tier)

```bash
az appservice plan update \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-plan-demo-ron \
  --sku S2
```

### Horizontal Scaling (Add Instances)

```bash
az appservice plan update \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-plan-demo-ron \
  --number-of-workers 2
```

## Monitoring and Diagnostics

### View Logs

```bash
az webapp log tail \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-demo-ron
```

### View Metrics in Application Insights

```bash
# Get Application Insights resource name
az monitor app-insights show \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-insights-demo-ron
```

Then view in Azure Portal or use:

```bash
az monitor metrics list-definitions \
  --resource /subscriptions/<subscription-id>/resourceGroups/rg-agentic-underwriting/providers/microsoft.insights/components/agentic-underwriting-insights-demo-ron
```

## Troubleshooting

### Application Won't Start

1. Check deployment logs:
   ```bash
   az webapp deployment log show \
     --resource-group rg-agentic-underwriting \
     --name agentic-underwriting-backend-demo-ron
   ```

2. Check App Service logs:
   ```bash
   az webapp log tail \
     --resource-group rg-agentic-underwriting \
     --name agentic-underwriting-backend-demo-ron
   ```

### CORS Errors

Verify CORS_ORIGINS environment variable matches frontend URL:

```bash
az webapp config appsettings list \
  --resource-group rg-agentic-underwriting \
  --name agentic-underwriting-backend-demo-ron | grep CORS_ORIGINS
```

### Storage Access Issues

Verify managed identity has correct role assignments:

```bash
az role assignment list \
  --resource-group rg-agentic-underwriting \
  --scope /subscriptions/<subscription-id>/resourceGroups/rg-agentic-underwriting/providers/Microsoft.Storage/storageAccounts/<storage-account-name>
```

## Cleanup

To remove all deployed resources:

```bash
az group delete \
  --resource-group rg-agentic-underwriting \
  --yes --no-wait
```

## Additional Resources

- [Azure App Service Documentation](https://learn.microsoft.com/en-us/azure/app-service/)
- [Bicep Template Reference](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/file-format)
- [Azure Managed Identity](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview)
- [Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/)
