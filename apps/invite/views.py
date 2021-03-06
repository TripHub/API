from django.db.models import Q

from rest_framework import viewsets, mixins, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import NotFound, ValidationError

from .models import Invite
from .serializers import InviteSerializer
from .constants import PENDING


class InvitePublicViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for non-authenticated access to a invitation.
    """
    permission_classes = (AllowAny,)
    serializer_class = InviteSerializer
    lookup_field = 'uid'

    def get_queryset(self):
        # only pending invitations should be visible
        return Invite.objects.pending()


class InviteViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet for listing, accepting, rejecting and cancelling invites.
    """
    serializer_class = InviteSerializer
    lookup_field = 'uid'

    def get_queryset(self):
        """
        Gets invites for trips user is involved in. Filters based on ?trip
        query param.
        """
        qs = Invite.objects.filter(
            Q(trip__owner=self.request.user) |
            Q(trip__members__in=[self.request.user]))
        trip_search = self.request.query_params.get('trip')
        if trip_search:
            qs = qs.filter(trip__uid=trip_search)
        return qs

    def validate_user_for_invite(self, invite):
        """
        Checks the requesting user is the invite's user.
        Raises not found if the user does not match.
        """
        if invite.email != self.request.user.email:
            raise NotFound()

    @list_route()
    def pending(self, request):
        """
        Returns a list of all pending invitations.
        """
        pending_invites = self.get_queryset().filter(status=PENDING)

        page = self.paginate_queryset(pending_invites)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(page, many=True)
        return Response(serializer.data)

    @detail_route()
    def cancel(self, request, uid=None):
        try:
            # get the pending invite from the user's scope
            invite = self.get_queryset().filter(status=PENDING).get(uid=uid)
            # ensure the user is the owner of the invite's trip
            if invite.trip.owner != self.request.user:
                raise PermissionError(
                    'Only the trip owner can cancel an invite.')
            invite.cancel()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Invite.DoesNotExist:
            raise NotFound()

    @detail_route()
    def accept(self, request, uid=None):
        try:
            # get the pending invite
            invite = Invite.objects.pending().get(uid=uid)
            self.validate_user_for_invite(invite)
            # check the user isn't already involved in the trip
            is_user_owner = invite.trip.owner == self.request.user
            is_user_member = invite.trip.members.filter(
                pk=self.request.user.pk).exists()
            if is_user_owner or is_user_member:
                raise ValidationError(
                    'User is already a member or owner of the trip.')
            # update the invite status
            invite.trip.add_member(self.request.user)
            invite.accept()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Invite.DoesNotExist:
            raise NotFound()

    @detail_route()
    def reject(self, request, uid=None):
        try:
            # get the pending invite
            invite = Invite.objects.pending().get(uid=uid)
            self.validate_user_for_invite(invite)
            invite.reject()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Invite.DoesNotExist:
            raise NotFound()
