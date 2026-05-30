CUSTOMER_SUPPORT_GROUP_NAME = "Customer Support"


def user_is_customer_support(user):
    return (
        getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and getattr(user, "is_superuser", False)
        and user.groups.filter(name=CUSTOMER_SUPPORT_GROUP_NAME).exists()
    )
