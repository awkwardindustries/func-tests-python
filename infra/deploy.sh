# #####################################
# Resource Group
# #####################################

RG=rg-func-test-python
LOC=southcentralus

# Create the resource group in which everything will land

az group create -g $RG -l $LOC

# #####################################
# Function App
# #####################################

FUNC_STORAGE=stfunctest13
FUNC_APPNAME=func-tests-python

# Storage Account

az storage account create \
  --resource-group $RG \
  --location $LOC \
  --sku Standard_LRS \
  --name $FUNC_STORAGE

# Python
# Note: Python v1 or v2 is set in the host.json
# runtime-version 3.9, 3.8, 3.7, or 3.6

az functionapp create \
  --resource-group $RG \
  --consumption-plan-location $LOC \
  --runtime python \
  --runtime-version 3.8 \
  --functions-version 4 \
  --os-type linux \
  --assign-identity '[system]' \
  --storage-account $FUNC_STORAGE \
  --name $FUNC_APPNAME

# Use system-assigned managed identity
# az functionapp identity assign \
#   --resource-group $RG \
#   --name $FUNC_APPNAME

# #####################################
# Cosmos DB
# #####################################

COSMOS_ACCOUNT=awkwardindustries
COSMOS_DATABASE=ToDoList
COSMOS_CONTAINER=Items

# Create Cosmos DB database account

az cosmosdb create \
  --resource-group $RG \
  --name $COSMOS_ACCOUNT

# Create DB and container

az cosmosdb sql database create \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --name $COSMOS_DATABASE

az cosmosdb sql container create \
  --resource-group $RG \
  --account-name $COSMOS_ACCOUNT \
  --database-name $COSMOS_DATABASE \
  --partition-key-path '/id' \
  --throughput 400 \
  --name $COSMOS_CONTAINER

# #####################################
# Cache for Redis
# #####################################

REDIS_ACCOUNT=awkwardindustries

# Create Cache for Redis

az redis create \
  --resource-group $RG \
  --location $LOC \
  --sku 'Standard' \
  --vm-size 'C1' \
  --name $REDIS_ACCOUNT

# #####################################
# Key Vault
# #####################################

KEY_VAULT=kv-func-test-13

# Create vault

az keyvault create \
  --resource-group $RG \
  --location $LOC \
  --enable-rbac-authorization \
  --name $KEY_VAULT

# Add secrets
az keyvault secret set \
  --vault-name $KEY_VAULT \
  --output none \
  --name "RedisHost" \
  --value $(az redis show -n $REDIS_ACCOUNT -g $RG -o tsv --query hostName)
az keyvault secret set \
  --vault-name $KEY_VAULT \
  --output none \
  --name "RedisPort" \
  --value $(az redis show -n $REDIS_ACCOUNT -g $RG -o tsv --query sslPort)
az keyvault secret set \
  --vault-name $KEY_VAULT \
  --output none \
  --name "RedisKey" \
  --value $(az redis list-keys -n $REDIS_ACCOUNT -g $RG -o tsv --query primaryKey)
az keyvault secret set \
  --vault-name $KEY_VAULT \
  --output none \
  --name "CosmosHost" \
  --value $(az cosmosdb show -n $COSMOS_ACCOUNT -g $RG -o tsv --query documentEndpoint)
az keyvault secret set \
  --vault-name $KEY_VAULT \
  --output none \
  --name "CosmosKey" \
  --value $(az cosmosdb keys list -n $COSMOS_ACCOUNT -g $RG -o tsv --query primaryMasterKey)

# #####################################
# RBAC
# #####################################

ASSIGNEE_ID=$(az functionapp identity show -n $FUNC_APPNAME -g $RG -o tsv --query "principalId")

# Assign Cosmos role(s)

COSMOS_SCOPE=$(az cosmosdb show -n $COSMOS_ACCOUNT -g $RG -o tsv --query id)

# Administer Cosmos DB...
# az role assignment create \
#   --assignee $ASSIGNEE_ID \
#   --role "Cosmos DB Account Reader Role" \
#   --scope $COSMOS_SCOPE
# az role assignment create \
#   --assignee $ASSIGNEE_ID \
#   --role "Cosmos DB Operator" \
#   --scope $COSMOS_SCOPE

az role assignment create \
  --assignee $ASSIGNEE_ID \
  --role "DocumentDB Account Contributor" \
  --scope $COSMOS_SCOPE

# Assign Cache for Redis role(s)

REDIS_SCOPE=$(az redis show -n $REDIS_ACCOUNT -g $RG -o tsv --query id)

az role assignment create \
  --assignee $ASSIGNEE_ID \
  --role "Redis Cache Contributor" \
  --scope $REDIS_SCOPE

# Assign Key Vault role(s)

KV_SCOPE=$(az keyvault show -n $KEY_VAULT -g $RG -o tsv --query id)

az role assignment create \
  --assignee $ASSIGNEE_ID \
  --role "Key Vault Secrets User" \
  --scope $KV_SCOPE

# Administer Key Vault...
# az role assignment create \
#   --assignee $ASSIGNEE_ID \
#   --role "Key Vault Administrator" \
#   --scope $KV_SCOPE
