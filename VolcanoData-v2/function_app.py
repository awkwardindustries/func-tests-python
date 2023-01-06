import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="GetItems")
@app.route(route="items") # HTTP Trigger
def test_function(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("GetItems (v2) function processed a request!!!")