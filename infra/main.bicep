param location string = resourceGroup().location
param environment string = 'demo'
param appName string = 'agentic-underwriting'

// App Service Plans
resource backendAppServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${appName}-backend-plan-${environment}'
  location: location
  sku: {
    name: 'F1'
    tier: 'Free'
    capacity: 1
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

resource frontendAppServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: '${appName}-frontend-plan-${environment}'
  location: location
  sku: {
    name: 'F1'
    tier: 'Free'
    capacity: 1
  }
  kind: 'linux'
  properties: {
    reserved: true
  }
}

// Backend App Service
resource backendAppService 'Microsoft.Web/sites@2024-04-01' = {
  name: '${appName}-backend-${environment}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: backendAppServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: true
      http20Enabled: true
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
      ]
    }
    httpsOnly: true
  }
}

// Frontend App Service
resource frontendAppService 'Microsoft.Web/sites@2024-04-01' = {
  name: '${appName}-frontend-${environment}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: frontendAppServicePlan.id
    siteConfig: {
      linuxFxVersion: 'NODE|20-lts'
      alwaysOn: true
      http20Enabled: true
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appSettings: [
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
      ]
    }
    httpsOnly: true
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${appName}-insights-${environment}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    RetentionInDays: 30
  }
}

// Key Vault for secrets
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: '${appName}-kv-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: {
      family: 'A'
      name: 'standard'
    }
    accessPolicies: [
      {
        tenantId: subscription().tenantId
        objectId: backendAppService.identity.principalId
        permissions: {
          secrets: ['get', 'list']
        }
      }
      {
        tenantId: subscription().tenantId
        objectId: frontendAppService.identity.principalId
        permissions: {
          secrets: ['get', 'list']
        }
      }
    ]
  }
}

// Storage Account for application data (with identity-based access)
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: '${take(replace(appName, '-', ''), 11)}${uniqueString(resourceGroup().id)}'
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// Blob container for storage
resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageAccount.name}/default/app-data'
  properties: {
    publicAccess: 'None'
  }
}

// Role assignment: Backend App Service - Storage Blob Data Contributor
resource backendStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, backendAppService.id, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: backendAppService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Role assignment: Frontend App Service - Storage Blob Data Reader
resource frontendStorageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, frontendAppService.id, '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1') // Storage Blob Data Reader
    principalId: frontendAppService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Log Analytics Workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${appName}-logs-${environment}'
  location: location
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Diagnostic Settings for Backend App Service
resource backendDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: backendAppService
  name: 'backend-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
      }
      {
        category: 'AppServiceApplicationLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Diagnostic Settings for Frontend App Service
resource frontendDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: frontendAppService
  name: 'frontend-diagnostics'
  properties: {
    workspaceId: logAnalyticsWorkspace.id
    logs: [
      {
        category: 'AppServiceHTTPLogs'
        enabled: true
      }
      {
        category: 'AppServiceConsoleLogs'
        enabled: true
      }
      {
        category: 'AppServiceApplicationLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// Outputs
output backendAppServiceId string = backendAppService.id
output backendAppServiceName string = backendAppService.name
output frontendAppServiceId string = frontendAppService.id
output frontendAppServiceName string = frontendAppService.name
output backendAppServiceUrl string = 'https://${backendAppService.properties.defaultHostName}'
output frontendAppServiceUrl string = 'https://${frontendAppService.properties.defaultHostName}'
output storageAccountName string = storageAccount.name
output storageAccountId string = storageAccount.id
output keyVaultName string = keyVault.name
output keyVaultId string = keyVault.id
output appInsightsId string = appInsights.id
output appInsightsInstrumentationKey string = appInsights.properties.InstrumentationKey
