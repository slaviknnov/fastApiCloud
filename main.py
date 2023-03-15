from fastapi import FastAPI
from mangum import Mangum

from custom_handlers import YCGateway

app = FastAPI()


@app.get("/")
async def root():
    return {"message": "Hello World"}


def handler(event, context):
    print(event)  # для отладки, что бы видно было в логах какой запрос приходит
    return Mangum(app, lifespan="off", custom_handlers=[YCGateway])(event, context)
