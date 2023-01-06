import json
import logging
import os
import azure.functions as func

from azure.cosmos.aio import CosmosClient
#from azure.identity import DefaultAzureCredential
from redis.asyncio import BlockingConnectionPool, Redis

#AZURE_CRED = DefaultAzureCredential()
COSMOS_HOST = os.getenv("CosmosHost")
COSMOS_KEY = os.getenv("CosmosKey")
COSMOS_DATABASE = os.getenv("CosmosDatabase")
COSMOS_CONTAINER = os.getenv("CosmosContainer")

REDIS_HOST = os.getenv("RedisHost")
REDIS_PORT = os.getenv("RedisPort")
REDIS_KEY = os.getenv("RedisKey")
REDIS_POOL = BlockingConnectionPool()

HEADERS = {
    "Content-type": "application/json"
}

async def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    if context and context.invocation_id:
        HEADERS["Azure_InvocationId"] = context.invocation_id

    # If "heartbeat" check, immediately return.
    if req.params.get("heartbeat"):
        return func.HttpResponse(
            body = json.dumps({
                "message": "Function GetDetails (v1) is alive!"
            }),
            status_code = 200,
            headers = HEADERS
        )

    lookup_id = req.params.get("lookup")
    if lookup_id:
        cached_item = await lookup_item_in_cache(lookup_id=lookup_id)
        if cached_item:
            # It's already cached. Return and exit.
            return func.HttpResponse(
                body = cached_item,
                status_code = 200,
                headers = HEADERS
            )
        else:
            # Deep lookup since it's not cached
            item = await lookup_item_in_store(lookup_id=lookup_id)
            if item:
                # Lookup successful
                res_body = item
                statusCode = 200
                # Add to cache for next time
                await set_item_in_cache(
                    lookup_id = lookup_id,
                    details = item
                )
            else:
                # Lookup failed cache & store
                res_body = { "message": "Record not found" }
                statusCode = 404
    else:
        # No 'lookup' param provided
        res_body = { "message": "Invalid input" }
        statusCode = 400

    return func.HttpResponse(
        body = json.dumps(res_body),
        status_code = statusCode,
        headers = HEADERS
    )

async def lookup_item_in_store(lookup_id):
    async with CosmosClient(COSMOS_HOST, COSMOS_KEY) as client: #(COSMOS_URI, AZURE_CRED)
        try:
            database = client.get_database_client(COSMOS_DATABASE)
            container = database.get_container_client(COSMOS_CONTAINER)
            # Query Cosmos for the item
            # Raises CosmosHttpResponseError if item not found or can't be retrieved
            item = await container.read_item(
                item = lookup_id,
                partition_key = lookup_id
            )
            return item
        except Exception as e:
            # Something raised an exception:
            # - get_database_client possibly raises CosmosResourceExistsError (? docs seem wrong)
            # - get_container_client possibly raises CosmosHttpResponseError
            # - read_item possibly raises CosmosHttpResponseError
            logging.error("Cosmos client error: " + str(e))
            return None

async def lookup_item_in_cache(lookup_id):
    async with Redis(
        connection_pool=REDIS_POOL,
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_KEY,
        ssl=True,
        socket_timeout=1,
        socket_connect_timeout=1
    ) as client:
        try:
            item = await client.get(lookup_id)
            # Returns value or None if the key doesn't exist.
            logging.info(f"Cache hit with item [{lookup_id}]? {item is not None}")
            return item
        except Exception as e:
            # Non-critical operation; eating any errors
            logging.error("Error checking cache: " + str(e))
            return None

async def set_item_in_cache(lookup_id, details):
    async with Redis(
        connection_pool=REDIS_POOL,
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_KEY,
        ssl=True,
        socket_timeout=1,
        socket_connect_timeout=1
    ) as client:
        try:
            result = await client.set(lookup_id, json.dumps(details))
            logging.info("Cached item [" + lookup_id + "]")
        except Exception as e:
            # Non-critical operation; eating any errors
            logging.error("Error caching item: " + str(e))
