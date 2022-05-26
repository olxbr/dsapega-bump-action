BASE_URL = "https://api.github.com{}"
GH_TOKEN = ""


def mocked_requests_get(*args, **kwargs):
    class MockResponse:
        def __init__(self, json_data, status_code):
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            return self.json_data

    print(kwargs["headers"]["Authorization"])
    if kwargs["headers"]["Authorization"] == f"token {GH_TOKEN}":
        if args[0] == BASE_URL.format("/repos/olxbr/tech-radar/languages"):
            return MockResponse({"kotlin": "5000", "python": "4000"}, 200)
        if args[0] == BASE_URL.format("/repos/olxbr/zero-lang-repo/languages"):
            return MockResponse({}, 200)
        if args[0] == BASE_URL.format("/repos/olxbr/tech-radar"):
            return MockResponse({"created_at": "2022-04-08T17:46:53Z"}, 200)
    else:
        return MockResponse(
            {
                "message": "Bad credentials",
                "documentation_url": "https://docs.github.com/rest",
            },
            401,
        )

    return MockResponse(None, 404)
