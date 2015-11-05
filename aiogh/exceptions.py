

class AioghException(Exception):
    pass


class HttpError(AioghException):

    def __init__(self, response):
        self.response = response


class UnknownState(AioghException):
    pass
