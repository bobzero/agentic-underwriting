#!/bin/bash

# Deployment script for Agentic Underwriting to Azure
# This script deploys the infrastructure and applications to the specified resource group

set -e

# Configuration
# You can override these via environment variables or CLI flags:
#   --resource-group, --location, --environment, --app-name
RESOURCE_GROUP="${RESOURCE_GROUP:-rg-agentic-underwriting}"
LOCATION="${LOCATION:-northcentralus}"
ENVIRONMENT="${ENVIRONMENT:-demo-ron}"
APP_NAME="${APP_NAME:-agentic-underwriting}"
BACKEND_PATH="./agentic-underwriting-backend"
FRONTEND_PATH="./agentic-underwriting-ui"
SKIP_INFRA="false"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        --location)
            LOCATION="$2"
            shift 2
            ;;
        --environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --app-name)
            APP_NAME="$2"
            shift 2
            ;;
        --skip-infra)
            SKIP_INFRA="true"
            shift
            ;;
        --help|-h)
            echo "Usage: ./deploy.sh [--resource-group <name>] [--location <azure-region>] [--environment <name>] [--app-name <name>] [--skip-infra]"
            echo ""
            echo "Defaults:"
            echo "  RESOURCE_GROUP=$RESOURCE_GROUP"
            echo "  LOCATION=$LOCATION"
            echo "  ENVIRONMENT=$ENVIRONMENT"
            echo "  APP_NAME=$APP_NAME"
            echo "  SKIP_INFRA=$SKIP_INFRA"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run './deploy.sh --help' for usage."
            exit 1
            ;;
    esac
done

echo "=========================================="
echo "Agentic Underwriting Deployment Script"
echo "=========================================="
echo ""
echo "Resource Group: $RESOURCE_GROUP"
echo "Location: $LOCATION"
echo "Environment: $ENVIRONMENT"
echo "Skip Infra: $SKIP_INFRA"
echo ""

# Check prerequisites
echo "[1/7] Checking prerequisites..."
command -v az &> /dev/null || { echo "Azure CLI is required but not installed."; exit 1; }
command -v zip &> /dev/null || { echo "zip is required but not installed."; exit 1; }

# Verify the user is logged in
if ! az account show &> /dev/null; then
    echo "Error: Not logged into Azure. Please run 'az login' first."
    exit 1
fi

CURRENT_SUB=$(az account show --query name -o tsv)
echo "✓ Logged into Azure subscription: $CURRENT_SUB"
echo ""

# Check resource group exists
echo "[2/7] Verifying resource group..."
if ! az group exists -n "$RESOURCE_GROUP" | grep -q true; then
    echo "Creating resource group $RESOURCE_GROUP..."
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
else
    echo "✓ Resource group $RESOURCE_GROUP already exists"
fi
echo ""

# Resolve app names/URLs and deploy infrastructure when enabled
BACKEND_APP="${APP_NAME}-backend-${ENVIRONMENT}"
FRONTEND_APP="${APP_NAME}-frontend-${ENVIRONMENT}"
BACKEND_URL="https://${BACKEND_APP}.azurewebsites.net"
FRONTEND_URL="https://${FRONTEND_APP}.azurewebsites.net"
APP_INSIGHTS_KEY=""

if [[ "$SKIP_INFRA" == "true" ]]; then
    echo "[3/7] Skipping infrastructure deployment (--skip-infra)"
    echo "  Backend App Service: $BACKEND_APP"
    echo "  Frontend App Service: $FRONTEND_APP"
    echo ""
else
    echo "[3/7] Deploying infrastructure with Bicep..."
    if INFRA_OUTPUT=$(az deployment group create \
        --resource-group "$RESOURCE_GROUP" \
        --template-file ./infra/main.bicep \
        --parameters location="$LOCATION" environment="$ENVIRONMENT" appName="$APP_NAME" \
        --query properties.outputs \
        -o json 2> /tmp/agentic_underwriting_infra_err.log); then

        BACKEND_APP=$(echo "$INFRA_OUTPUT" | jq -r '.backendAppServiceName.value')
        FRONTEND_APP=$(echo "$INFRA_OUTPUT" | jq -r '.frontendAppServiceName.value')
        BACKEND_URL=$(echo "$INFRA_OUTPUT" | jq -r '.backendAppServiceUrl.value')
        FRONTEND_URL=$(echo "$INFRA_OUTPUT" | jq -r '.frontendAppServiceUrl.value')
        APP_INSIGHTS_KEY=$(echo "$INFRA_OUTPUT" | jq -r '.appInsightsInstrumentationKey.value')

        echo "✓ Infrastructure deployed successfully"
        echo "  Backend App Service: $BACKEND_APP"
        echo "  Frontend App Service: $FRONTEND_APP"
        echo ""
    else
        echo "⚠ Infrastructure deployment failed; continuing with existing App Services."
        cat /tmp/agentic_underwriting_infra_err.log

        if ! az webapp show --resource-group "$RESOURCE_GROUP" --name "$BACKEND_APP" > /dev/null 2>&1; then
            echo "Error: Backend App Service not found: $BACKEND_APP"
            exit 1
        fi
        if ! az webapp show --resource-group "$RESOURCE_GROUP" --name "$FRONTEND_APP" > /dev/null 2>&1; then
            echo "Error: Frontend App Service not found: $FRONTEND_APP"
            exit 1
        fi

        echo "✓ Using existing App Services"
        echo "  Backend App Service: $BACKEND_APP"
        echo "  Frontend App Service: $FRONTEND_APP"
        echo ""
    fi
fi

# Build and deploy backend
echo "[4/7] Building and deploying backend..."
cd "$BACKEND_PATH"

# Install dependencies
pip install -q -r requirements.txt

# Create deployment package
rm -f backend.zip
zip -r -q backend.zip . -x "*.git*" "__pycache__*" "*.pyc" ".env" ".venv*" "venv*"

# Deploy to App Service
az webapp deployment source config-zip \
    --resource-group "$RESOURCE_GROUP" \
    --name "$BACKEND_APP" \
    --src backend.zip > /dev/null

echo "✓ Backend deployed to: $BACKEND_URL"
cd - > /dev/null
echo ""

# Build and deploy frontend
echo "[5/7] Building and deploying frontend..."
cd "$FRONTEND_PATH"

# Install dependencies
npm ci -q

# Build
npm run build

# Create deployment package
rm -f frontend.zip
zip -r -q frontend.zip . -x "*.git*" "node_modules*" ".next*" ".env*" "*.md"

# Deploy to App Service
az webapp deployment source config-zip \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FRONTEND_APP" \
    --src frontend.zip > /dev/null

echo "✓ Frontend deployed to: $FRONTEND_URL"
cd - > /dev/null
echo ""

# Configure environment variables
echo "[6/7] Configuring application settings..."

# Backend configuration
BACKEND_SETTINGS=(
    "CORS_ORIGINS=https://${FRONTEND_URL#https://}"
    "OTEL_SERVICE_NAME=agentic-underwriting-backend"
    "SCM_DO_BUILD_DURING_DEPLOYMENT=true"
    "PYTHON_VERSION=3.11"
)

if [[ -n "$APP_INSIGHTS_KEY" && "$APP_INSIGHTS_KEY" != "null" ]]; then
    BACKEND_SETTINGS+=("APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=$APP_INSIGHTS_KEY")
fi

az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$BACKEND_APP" \
    --settings "${BACKEND_SETTINGS[@]}" > /dev/null

# Frontend configuration
az webapp config appsettings set \
    --resource-group "$RESOURCE_GROUP" \
    --name "$FRONTEND_APP" \
    --settings \
        NEXT_PUBLIC_API_BASE_URL="$BACKEND_URL" \
        NEXT_PUBLIC_API_URL="$BACKEND_URL" > /dev/null

echo "✓ Application settings configured"
echo ""

# Display summary
echo "[7/7] Deployment Summary"
echo "=========================================="
echo "Frontend URL: $FRONTEND_URL"
echo "Backend URL: $BACKEND_URL"
echo ""
echo "Next steps:"
echo "1. Configure any additional environment variables (LLM provider, etc.) in App Service Configuration"
echo "2. Use Azure Key Vault (already deployed) for sensitive secrets"
echo "3. Test the application at: $FRONTEND_URL"
echo ""
echo "Resources created:"
echo "- Resource Group: $RESOURCE_GROUP"
echo "- Backend App Service: $BACKEND_APP"
echo "- Frontend App Service: $FRONTEND_APP"
echo "- App Service Plans (2)"
echo "- Application Insights"
echo "- Key Vault"
echo "- Storage Account (with identity-based access)"
echo "- Log Analytics Workspace"
echo ""
echo "✓ Deployment completed successfully!"
