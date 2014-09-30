import datetime
import random
import hashlib

from django.conf import settings
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.db import models
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone
from django.contrib.auth.tokens import default_token_generator

__all__ = ['Invitation']

class InvitationManager(models.Manager):
    def create_invitation(self, user, email):
        """
        Create an ``Invitation`` and returns it.

        The code for the ``Invitation`` will be a SHA1 hash, generated
        from a combination of the ``User``'s username and a random salt.
        """

        kwargs = {'from_user': user, 'email': email}
        date_invited = datetime.datetime.now()
        kwargs['date_invited'] = date_invited
        #kwargs['groups':groups]
        kwargs['expiration_date'] = date_invited + datetime.timedelta(settings.ACCOUNT_INVITATION_DAYS)
        kwargs['code'] = default_token_generator.make_token(user)
        invite = self.create(**kwargs)
        return invite

    def remaining_invitations_for_user(self, user):
        """ Returns the number of remaining invitations for a given ``User``
        if ``INVITATIONS_PER_USER`` has been set.
        """
        if hasattr(settings, 'INVITATIONS_PER_USER'):
            inviteds_count = self.filter(from_user=user).count()
            remaining_invitations = settings.INVITATIONS_PER_USER - inviteds_count
            if remaining_invitations < 0:
                # Possible for admin to change INVITATIONS_PER_USER
                # to something lower than the initial setting, resulting
                # in a negative value
                return 0
            return remaining_invitations

    def delete_expired_invitations(self):
        """
        Deletes all unused ``Invitation`` objects that are past the expiration date
        """
        self.filter(expiration_date__lt=datetime.datetime.now(), used=False).delete()


class Invitation(models.Model):
    code = models.CharField(_('invitation code'), max_length=40)
    date_invited = models.DateTimeField(_('date invited'))
    expiration_date = models.DateTimeField()
    used = models.BooleanField(default=False)
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='invitations_sent')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, related_name='invitation_received')
    email = models.EmailField(unique=True)

    objects = InvitationManager()

    def __unicode__(self):
        return u"Invitation from %s to %s" % (self.from_user.username, self.email)

    def expired(self):
        expiration_date = self.expiration_date
        if not timezone.is_aware(expiration_date):
            expiration_date = timezone.make_aware(expiration_date, timezone.get_default_timezone())
        return expiration_date < timezone.now()

    def send(self, from_email=settings.DEFAULT_FROM_EMAIL,
        subject_template='invitation/invitation_email_subject.txt',
        message_template='invitation/invitation_email.txt'):

        """
        Send an invitation email.
        """
        current_site = Site.objects.get_current()

        subject = render_to_string(subject_template,
                                   {'invitation': self,
                                    'site': current_site})
        # Email subject *must not* contain newlines
        subject = ''.join(subject.splitlines())

        message = render_to_string(message_template,
                                   {'invitation': self,
                                    'expiration_days': settings.ACCOUNT_INVITATION_DAYS,
                                    'site': current_site})

        send_mail(subject, message, from_email, [self.email])

    #Extends the invitation for X days from the time it's called, where X is the account_invitation_days
    def extend(self):
        date_now = datetime.datetime.now()
        extend_time = timedelta(days=settings.ACCOUNT_INVITATION_DAYS)
        self.expiration_date = date_now + extend_time
        self.save()



