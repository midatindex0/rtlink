from gql.transport.exceptions import TransportQueryError as GQLTE


class RtLinkException(Exception):
    pass


class TransportQueryError(RtLinkException):
    def __init__(self, e: GQLTE, *args, **kwargs):
        self.e: GQLTE = e
        super().__init__(*args, **kwargs)
