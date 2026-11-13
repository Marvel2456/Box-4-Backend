def get_client_platform(request):
    """
    Returns the normalized client platform from the 'X-Client-Platform' header
    ('ios', 'android', etc.), or None if not provided.
    """
    if not request:
        return None

    platform = None
    headers = getattr(request, 'headers', None)
    if headers is not None:
        platform = headers.get('X-Client-Platform') or headers.get('x-client-platform')

    if not platform and hasattr(request, 'META'):
        platform = request.META.get('HTTP_X_CLIENT_PLATFORM')

    if not platform:
        return None

    cleaned = str(platform).strip().lower()
    return cleaned or None


def is_ios_client(request):
    """
    Returns True only when the client explicitly identifies as 'ios' via X-Client-Platform.
    If the header is missing or 'android', returns False to preserve existing behavior.
    """
    return get_client_platform(request) == 'ios'

