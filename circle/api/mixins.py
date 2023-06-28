from rest_framework.mixins import CreateModelMixin
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework import status


class BulkCreateCircleInviteMixin(CreateModelMixin):
    """
    Either create a single or many model instances in bulk by using the
    Serializer's ``many=True``

    .. note::
        This mixin uses the same method to create model instances
        as ``CreateModelMixin`` because both non-bulk and bulk
        requests will use ``POST`` request method.
    """

    def create(self, request, *args, **kwargs):
        bulk = isinstance(request.data, list)
        if not bulk:
            serializer = super(
                BulkCreateCircleInviteMixin, self).create(request, *args, **kwargs)
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
                    data = {
                        'index': i, 'data': serializer.data,
                        'msg': "Group Invite successfull!"
                    }
                    results.append(data)
                else:
                    data = {
                        'index': i,
                        'msg': "Group Invite Unsuccessfull!",
                        'error': serializer.errors
                    }
                    results.append(data)
            return Response(results)
