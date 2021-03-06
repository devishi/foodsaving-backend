from django.contrib.auth import get_user_model
from django.db.models import Q
from django.dispatch import Signal
from django.utils import timezone
from rest_framework import filters
from rest_framework import mixins
from rest_framework import status
from rest_framework.decorators import list_route
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from foodsaving.users.permissions import IsSameUser, IsNotVerified
from foodsaving.users.serializers import UserSerializer, VerifyMailSerializer
from foodsaving.utils.mixins import PartialUpdateModelMixin

pre_user_delete = Signal(providing_args=['user'])


class UserViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    PartialUpdateModelMixin,
    mixins.DestroyModelMixin,
    mixins.ListModelMixin,
    GenericViewSet
):
    """
    Users

    # Query parameters
    - `?search` - search in `display_name`
    """
    queryset = get_user_model().objects
    serializer_class = UserSerializer
    filter_backends = (filters.SearchFilter,)
    permission_classes = (IsSameUser,)
    search_fields = ('display_name',)

    def get_permissions(self):
        if self.action == 'create':
            self.permission_classes = (AllowAny,)
        elif self.action in ('list', 'retrieve'):
            self.permission_classes = (IsAuthenticated,)

        return super().get_permissions()

    def get_queryset(self):
        users_groups = self.request.user.groups.values('id')
        return self.queryset.filter(Q(groups__in=users_groups) | Q(id=self.request.user.id)).distinct()

    def perform_destroy(self, user):
        """
        To keep historic pickup infos, don't delete this user, but delete it from the database.
        Removal from group and future pickups is handled via the signal.
        """
        pre_user_delete.send(sender=self.__class__, user=user)
        user.description = ''
        user.set_unusable_password()
        user.mail = None
        user.is_active = False
        user.is_staff = False
        user.activation_key = ''
        user.key_expires_at = None
        user.mail_verified = False
        user.unverified_email = None
        user.deleted_at = timezone.now()
        user.deleted = True
        user.save()

    @list_route(
        methods=['POST'],
        permission_classes=(IsNotVerified, IsAuthenticated),
        serializer_class=VerifyMailSerializer
    )
    def verify_mail(self, request, pk=None):
        """
        requires "key" parameter
        """
        self.check_object_permissions(request, request.user)
        serializer = self.get_serializer(request.user, request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response()

    @list_route(
        methods=['POST'],
        permission_classes=(IsAuthenticated,)
    )
    def resend_verification(self, request, pk=None):
        "resend verification mail"
        if request.user.mail_verified:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'Already verified'})
        request.user.send_verification_code()
        return Response(status=status.HTTP_200_OK)

    @list_route(
        methods=['POST']
    )
    def reset_password(self, request, pk=None):
        """
        send a request with 'email' to this endpoint to get a new password mailed

        to prevent information leaks, also returns success if the mail doesn't exist
        """
        request_email = request.data.get('email')
        if not request_email:
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'mail address is not provided'})
        try:
            user = get_user_model().objects.get(email=request_email)
        except get_user_model().DoesNotExist:
            # don't leak valid mail addresses
            return Response(status=status.HTTP_204_NO_CONTENT)
        if not user.mail_verified:
            # I think we can leave this in here, unverified addresses are not so useful to spammers
            return Response(status=status.HTTP_400_BAD_REQUEST,
                            data={'error': 'mail is not verified'})
        user.reset_password()
        return Response(status=status.HTTP_204_NO_CONTENT)
