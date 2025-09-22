class FinnhubAPIException(Exception):
    def __init__(self, response):
        super(FinnhubAPIException, self).__init__()

        self.code = 0

        try:
            json_response = response.json()
        except ValueError:
            self.message = "JSON error message from Finnhub: {}".format(response.text)
        else:
            if "error" not in json_response:
                self.message = "Wrong json format from FinnhubAPI"
            else:
                self.message = json_response["error"]

        self.status_code = response.status_code
        self.response = response

    def __str__(self):
        return "FinnhubAPIException(status_code: {}): {}".format(self.status_code, self.message)


class FinnhubRequestException(Exception):
    def __init__(self, message):
        super(FinnhubRequestException, self).__init__()
        self.message = message

    def __str__(self):
        return "FinnhubRequestException: {}".format(self.message)
