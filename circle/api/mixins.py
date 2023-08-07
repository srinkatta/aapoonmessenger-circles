from rest_framework.mixins import CreateModelMixin
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework import status


class BulkCreateCircleInviteMixin(CreateModelMixin):
    """
    Mixin to allow the creation of either a single or multiple model instances in bulk.

    By using this mixin, a view can handle both non-bulk and bulk requests to create
    model instances. The mixin uses the same method as ``CreateModelMixin`` to handle
    the creation of non-bulk requests.

    Usage:
        - For non-bulk requests, use the regular CreateModelMixin's ``create`` method.
        - For bulk requests, provide a list of data in the request body, and the view
          will create multiple model instances based on the provided data.

    .. note::
        For bulk requests, the request data should be provided as a list of dictionaries,
        each representing the data for a single model instance.

    Example:
        Non-bulk request:
        ```
        {
            "sender": 1,
            "recipient": 2,
            "circle": 3
        }
        ```

        Bulk request:
        ```
        [
            {"sender": 1, "recipient": 2, "circle": 3},
            {"sender": 4, "recipient": 5, "circle": 6},
            ...
        ]
        ```

    Response:
        - For non-bulk requests, the regular response from CreateModelMixin's ``create`` method.
        - For bulk requests, a list of results indicating the success or failure of each
          individual model instance creation.

    Note:
        - For bulk requests, the mixin uses JSONRenderer for the response to ensure proper
          serialization of the results.
        - If any of the model instances fail to be created due to invalid data, the response
          will contain information about the errors for each failed instance.
    """

    def create(self, request, *args, **kwargs):
        bulk = isinstance(request.data, list)
        if not bulk:
            serializer = super(BulkCreateCircleInviteMixin, self).create(request, *args, **kwargs)
            return serializer
        else:
            self.renderer_classes = (JSONRenderer,)
            request.accepted_renderer = JSONRenderer()
            list_data = request.data
            results = []
            for i, item in enumerate(list_data):
                serializer = self.get_serializer(data=item)
                if serializer.is_valid():
                    serializer.save()
                    data = {"index": i, "data": serializer.data, "msg": "Group Invite successfull!"}
                    results.append(data)
                else:
                    data = {
                        "index": i,
                        "msg": "Group Invite Unsuccessfull!",
                        "error": serializer.errors,
                    }
                    results.append(data)
            return Response(results)
