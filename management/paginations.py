from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.exceptions import APIException
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse


#
class CustomLimitOffsetPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 30
    limit_query_param = "limit"
    offset_query_param = "start"

    def get_offset(self, request: Request, view=None):
        try:
            return int(request.query_params.get(self.offset_query_param, 0))
        except (ValueError, TypeError):
            raise APIException(
                detail={self.offset_query_param: "Must be a valid integer."}
            )

    def get_limit(self, request: Request):
        try:
            return int(
                request.query_params.get(self.limit_query_param, self.default_limit)
            )
        except (ValueError, TypeError):
            raise APIException(detail={self.limit_query_param: "Must be a valid integer."})

    def get_next_link(self):
        if self.offset + self.limit >= self.count:
            return None

        url = self.request.build_absolute_uri()
        offset = self.offset + self.limit
        query_params = {
            self.offset_query_param: offset,
            self.limit_query_param: self.limit,
        }

        url_parts = list(urlparse(url))
        query = dict(parse_qsl(url_parts[4]))
        query.update(query_params)
        url_parts[4] = urlencode(query)

        return urlunparse(url_parts)

    def get_previous_link(self):
        if self.offset <= 0:
            return None

        url = self.request.build_absolute_uri()
        offset = self.offset - self.limit
        if offset < 0:
            offset = 0

        query_params = {
            self.offset_query_param: offset,
            self.limit_query_param: self.limit,
        }

        url_parts = list(urlparse(url))
        query = dict(parse_qsl(url_parts[4]))
        query.update(query_params)
        url_parts[4] = urlencode(query)

        return urlunparse(url_parts)

    def paginate_queryset(self, queryset, request, view=None):
        self.request = request
        return super().paginate_queryset(queryset, request, view)

    def get_paginated_response(self, data):
        return Response(
            {
                "links": {
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                },
                "count": self.count,
                "results": data,
            }
        )
