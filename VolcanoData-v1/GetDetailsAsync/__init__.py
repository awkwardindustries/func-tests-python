import json
import logging
import os
import redis
import azure.functions as func

from azure.cosmos.aio import CosmosClient
#from azure.identity import DefaultAzureCredential

#AZURE_CRED = DefaultAzureCredential()

COSMOS_HOST = os.getenv("CosmosHost")
COSMOS_KEY = os.getenv("CosmosKey")
COSMOS_DATABASE = os.getenv("CosmosDatabase")
COSMOS_CONTAINER = os.getenv("CosmosContainer")

REDIS_HOST = os.getenv("RedisHost")
REDIS_PORT = os.getenv("RedisPort")
REDIS_KEY = os.getenv("RedisKey")
REDIS_CLIENT = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    password=REDIS_KEY,
    ssl=True,
    socket_timeout=1,
    socket_connect_timeout=1
)

HEADERS = {
    "Content-type": "application/json"
}

async def main(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    try:
        if context and context.invocation_id:
            HEADERS["Azure_InvocationId"] = context.invocation_id
        
        if req.method == "GET":
            if req.params.get("heartbeat"):
                return func.HttpResponse(
                    body = json.dumps({
                        "message": "Function GetDetails (v1) is alive!"
                    }),
                    status_code = 200,
                    headers = HEADERS
                )
            # Else, not a heartbeat check
            lookup_id = req.params.get("lookup")
            if lookup_id:
                try:
                    cached_item = get_item(lookup_id = lookup_id)
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
                                item = lookup_id,
                                partition_key = lookup_id
                            )
                            # Close the Cosmos client
                            await cosmos_client.close()
                            # Add whatever was retrieved to cache
                            set_item(
                                lookup_id = lookup_id,
                                details = res_body
                            )
                            # Check what was received in case not found
                            if res_body:
                                statusCode = 200
                            else:
                                raise Exception("Item not found")
                        except Exception as e:
                            # Something raised an exception (lookup failed?)
                            # Close the Cosmos client
                            logging.error("Cosmos client error: " + str(e))
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
                # No 'name' param provided
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

def get_item(lookup_id):
    try:
        item = REDIS_CLIENT.get(lookup_id)
        if item:
            logging.info("Item [" + lookup_id + "] found in cache")
            return item
        else:
            logging.info("Item [" + lookup_id + "] NOT in cache")
            return None
    except Exception as e:
        logging.error("Error checking cache: " + str(e))
        return None

def set_item(lookup_id, details):
    try:
        result = REDIS_CLIENT.set(lookup_id, json.dumps(details))
        if result:
            logging.info("Cached item [" + lookup_id + "]")
        else:
            raise("Caching item " + lookup_id + " failed")
    except Exception as e:
        # Is this catching line 141 (raise catcching item failed)
        # too? Or only exceptions from client.set?
        logging.error("Error caching item: " + str(e))