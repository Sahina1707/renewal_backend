from django.utils import translation
from rest_framework_simplejwt.authentication import JWTAuthentication

class UserLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Try to get the user from the JWT Token manually
        user = self.get_jwt_user(request)

        # 2. If we found a user, check their DB settings
        if user:
            try:
                # Access the related user_settings via the user object
                settings = getattr(user, 'general_settings', None)
                if settings and settings.language:
                    translation.activate(settings.language)
                    request.LANGUAGE_CODE = settings.language
            except Exception:
                pass

        response = self.get_response(request)
        translation.deactivate()
        return response

    def get_jwt_user(self, request):
        """
        Helper to extract user from JWT header because 
        request.user is not set yet in Middleware.
        """
        try:
            # This checks the 'Authorization' header
            auth_result = JWTAuthentication().authenticate(request)
            if auth_result:
                return auth_result[0] # Return the User object
        except Exception:
            pass
        
        # Fallback: If they use standard login (Admin panel), request.user works
        if request.user.is_authenticated:
            return request.user
            
        return None