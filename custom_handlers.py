from typing import Any

from fastapi.openapi.models import Response
from mangum.handlers.api_gateway import _handle_multi_value_headers_for_request, _encode_query_string_for_apigw
from mangum.handlers.utils import maybe_encode_body, strip_api_gateway_path, get_server_and_port, \
    handle_base64_response_body, handle_multi_value_headers
from mangum.types import LambdaEvent, LambdaContext, LambdaConfig, LambdaHandler
from starlette.types import Scope


class YCGateway(LambdaHandler):
    @classmethod
    def infer(cls, event: LambdaEvent, context: LambdaContext, config: LambdaConfig) -> bool:
        return "X-Serverless-Gateway-Id" in event['headers'] and "requestContext" in event

    def __init__(self, event: LambdaEvent, context: LambdaContext, config: LambdaConfig, *args: Any) -> None:
        super().__init__(*args)
        self.event = event
        self.context = context
        self.config = config

    @property
    def body(self) -> bytes:
        return maybe_encode_body(
            self.event.get("body", b""),
            is_base64=self.event.get("isBase64Encoded", False),
        )

    @property
    def scope(self) -> Scope:
        request_context = self.event["requestContext"]

        headers = _handle_multi_value_headers_for_request(self.event)
        source_ip = request_context["identity"]["sourceIp"]
        path = self.event["headers"]['X-Envoy-Original-Path']
        http_method = self.event["httpMethod"]
        query_string = _encode_query_string_for_apigw(self.event)
        if self.event.get("cookies"):
            headers["cookie"] = "; ".join(self.event.get("cookies", []))

        path = strip_api_gateway_path(path, api_gateway_base_path=self.config["api_gateway_base_path"])
        server = get_server_and_port(headers)
        client = (source_ip, 0)
        return {
            "type": "http",
            "method": http_method,
            "http_version": "1.1",
            "headers": [[k.encode(), v.encode()] for k, v in headers.items()],
            "path": path.split('?')[0],
            "raw_path": None,
            "root_path": "",
            "scheme": headers.get("x-forwarded-proto", "https"),
            "query_string": query_string,
            "server": server,
            "client": client,
            "asgi": {"version": "3.0", "spec_version": "2.0"},
            "aws.event": self.event,
            "aws.context": self.context,
            "path_params": self.event.get("path_params", {}),
            "user": request_context.get("authorizer", {}),
        }

    def __call__(self, response: Response) -> dict:
        finalized_headers, multi_value_headers = handle_multi_value_headers(
            response["headers"]
        )
        finalized_body, is_base64_encoded = handle_base64_response_body(
            response["body"], finalized_headers, self.config["text_mime_types"]
        )

        result = {
            "statusCode": response["status"],
            "headers": finalized_headers,
            "multiValueHeaders": multi_value_headers,
            "body": finalized_body,
            "isBase64Encoded": is_base64_encoded,
        }
        return result
