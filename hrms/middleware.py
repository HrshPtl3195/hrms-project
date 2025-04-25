from django.shortcuts import redirect
from django.contrib.auth.middleware import AuthenticationMiddleware

class PreventBackMiddleware:
    """Middleware to force users to re-authenticate after logout"""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Ensure request has 'user' attribute before using it
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            request.session.flush()  # Ensures session is fully wiped

        response = self.get_response(request)

        # Prevent browser caching of the page
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        return response
