# from django.contrib.auth.backends import BaseBackend
# from django.contrib.auth.hashers import check_password
# from .models import Users

# class EmailAuthBackend(BaseBackend):
#     def authenticate(self, request, username=None, password=None):  # Changed 'email' to 'username'
#         try:
#             user = Users.objects.get(email=username)  # username is used as the email
#             print(user, password, user.password_hash)
#             if password == user.password_hash:
#                 return user
#         except Users.DoesNotExist:
#             return None

#     def get_user(self, user_id):
#         try:
#             return Users.objects.get(pk=user_id)
#         except Users.DoesNotExist:
#             return None


from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from core.models import Users  # Ensure you import your Users model

class EmailAuthBackend(BaseBackend):
    """Authenticate using email and password"""

    def authenticate(self, request, username=None, password=None):
        try:
            user = Users.objects.get(email=username)  # Fetch user by email
            if check_password(password, user.password_hash):  # ✅ Compare hashed password
            # if password == user.password_hash:
                print(user, password)
                return user
        except Users.DoesNotExist:
            return None

    def get_user(self, user_id):
        try:
            return Users.objects.get(pk=user_id)
        except Users.DoesNotExist:
            return None
