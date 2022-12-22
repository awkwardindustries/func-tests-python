import logging

import azure.functions as func
import json
import redis

from azure.cosmos.aio import CosmosClient
from azure.identity import DefaultAzureCredential

AZURE_CRED = DefaultAzureCredential()

COSMOS_HOST = "https://awkwardindustries.documents.azure.com:443/"
COSMOS_KEY = ""
COSMOS_DATABASE = "ToDoList"
COSMOS_CONTAINER = "Items"

REDIS_HOST = ".redis.cache.windows.net"
REDIS_PORT = "6380"
REDIS_KEY = ""
REDIS_CLIENT = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_KEY,
    ssl=True,
    socket_timeout=1,
    socket_connect_timeout=1
)

HEADERS = {
    "Content-type": "application/json",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1",
    "Content-Security-Policy": "default-src 'self'",
    "Strict-Transport-Security": "max-age=86400"
}

async def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    try:
        if context and context.invocation_id:
            HEADERS["Azure_InvocationId"] = context.invocation_id
        
        if req.method == "GET":
            if req.params.get("heartbeat"):
                return func.HttpResponse(
                    body = json.dumps({
                        "message": "Function GetItems (v1) is alive!"
                    }),
                    status_code = 200,
                    headers = HEADERS
                )
            # Else, not a heartbeat check
            item_id = req.params.get("id")
            if item_id:
                try:
                    cached_item = get_item(id = item_id)
                    if cached_item:
                        return func.HttpResponse(
                            body = cached_item,
                            status_code = 200,
                            headers = HEADERS
                        )
                    else:
                        cosmos_client = CosmosClient(COSMOS_HOST, COSMOS_KEY)
                        # cosmos_client = CosmosClient(COSMOS_URI, AZURE_CRED)
                        database = cosmos_client.get_database_client(COSMOS_DATABASE)
                        container = database.get_container_client(COSMOS_CONTAINER)
                        
                        try:
                            # Query Cosmos for the item
                            res_body = await container.read_item(
                                item = COSMOS_CONTAINER,
                                partition_key = item_id
                            )
                            # Close the Cosmos client
                            await cosmos_client.close()
                            # Add whatever was retrieved to cache
                            set_item(
                                id = item_id,
                                details = res_body
                            )
                            # Check what was received in case not found
                            if res_body:
                                statusCode = 200
                            else:
                                raise Exception("Item not found")
                        except:
                            # Something raised an exception (lookup failed?)
                            # Close the Cosmos client
                            await cosmos_client.close()
                            res_body = {
                                "message": "Record not found"
                            }
                            statusCode = 404
                except Exception as e:
                    # Exception raised in:
                    #   cache lookup?
                    #   Cosmos client initialization?
                    logging.error("Cache/Init error: " + str(e))
                    res_body = {
                        "message": "Record not found"
                    }
                    statusCode = 404
            else:
                # No 'id' param provided
                res_body = {
                    "message": "Invalid input"
                }
                statusCode = 400
        else:
            # Not a GET
            res_body = {
                "message": "Method not supported"
            }
            statusCode = 405

    except Exception as e:
        logging.error("Root error: " + str(e))
        res_body = {
            "message": "System error"
        }
        statusCode = 500

    return func.HttpResponse(
        body = json.dumps(res_body),
        status_code = statusCode,
        headers = HEADERS
    )

def get_item(id):
    try:
        item=REDIS_CLIENT.get(id)
        if item:
            logging.info("Item [" + id + "] found in cache")
            return item
        else:
            logging.info("Item [" + id + "] NOT in cache")
            return None
    except Exception as e:
        logging.error("Error checking cache: " + str(e))
        return None

def set_item(id, details):
    try:
        result = REDIS_CLIENT.set(id, json.dumps(details))
        if result:
            logging.info("Cached item [" + id + "]")
        else:
            raise("Caching item " + id + " failed")
    except Exception as e:
        # Is this catching line 141 (raise catcching item failed)
        # too? Or only exceptions from client.set?
        logging.error("Error caching item: " + str(e))