"""Keep authenticated API facts out of browser and intermediary caches."""


def private_api_responses(get_response):
    def respond(request):
        response = get_response(request)
        if request.path_info.startswith('/api/v1/'):
            response['Cache-Control'] = 'no-store'
        return response
    return respond
