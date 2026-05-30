import getpass
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from portal.support_auth import CUSTOMER_SUPPORT_GROUP_NAME


class Command(BaseCommand):
    help = "Create or update the dedicated customer-support Django superuser."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="customer_support")
        parser.add_argument("--email", default="support@stoneodds.local")
        parser.add_argument("--password", default=None)
        parser.add_argument(
            "--noinput",
            action="store_true",
            help="Do not prompt. Use --password or CUSTOMER_SUPPORT_PASSWORD to set a password.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        email = options["email"]
        password = options["password"] or os.getenv("CUSTOMER_SUPPORT_PASSWORD")

        user = User.objects.filter(username=username).first()
        created = user is None
        if created:
            user = User(username=username)

        user.email = email
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True

        if password:
            self._set_validated_password(user, password)
        elif created or not self._has_real_password(user):
            if options["noinput"]:
                raise CommandError("A password is required for the support superuser.")
            self._prompt_for_password(user)

        user.save()
        group, _ = Group.objects.get_or_create(name=CUSTOMER_SUPPORT_GROUP_NAME)
        user.groups.add(group)

        action = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} support superuser '{username}' in the '{CUSTOMER_SUPPORT_GROUP_NAME}' group."
            )
        )

    def _prompt_for_password(self, user):
        while True:
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Password (again): ")
            if password != confirm:
                self.stderr.write("Passwords do not match.")
                continue
            self._set_validated_password(user, password)
            return

    def _has_real_password(self, user):
        return bool(user.password) and user.has_usable_password()

    def _set_validated_password(self, user, password):
        try:
            validate_password(password, user)
        except ValidationError as exc:
            raise CommandError("\n".join(exc.messages)) from exc
        user.set_password(password)
