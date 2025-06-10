from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import requests
import os
import json

app = Flask(__name__)
CORS(app)

# Service URLs
PACKAGE_SERVICE_URL = os.getenv('PACKAGE_SERVICE_URL', 'http://localhost:5001')
DELIVERY_SERVICE_URL = os.getenv('DELIVERY_SERVICE_URL', 'http://localhost:5002')
USER_SERVICE_URL = os.getenv('USER_SERVICE_URL', 'http://localhost:5003')

def proxy_request(service_url, path, method='GET', data=None, params=None):
    """Proxy requests to microservices"""
    try:
        url = f"{service_url}{path}"
        
        if method == 'GET':
            response = requests.get(url, params=params)
        elif method == 'POST':
            response = requests.post(url, json=data)
        elif method == 'PUT':
            response = requests.put(url, json=data)
        elif method == 'DELETE':
            response = requests.delete(url)
        else:
            return jsonify({'error': 'Unsupported method'}), 400
        
        return Response(
            response.content,
            status=response.status_code,
            headers=dict(response.headers)
        )
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Service unavailable: {str(e)}'}), 503

@app.route('/health', methods=['GET'])
def health_check():
    """Gateway health check"""
    services_health = {}
    
    # Check each service
    services = {
        'package-service': PACKAGE_SERVICE_URL,
        'delivery-service': DELIVERY_SERVICE_URL,
        'user-service': USER_SERVICE_URL
    }
    
    for service_name, service_url in services.items():
        try:
            response = requests.get(f"{service_url}/health", timeout=5)
            services_health[service_name] = {
                'status': 'healthy' if response.status_code == 200 else 'unhealthy',
                'response_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            services_health[service_name] = {
                'status': 'unhealthy',
                'error': str(e)
            }
    
    overall_status = 'healthy' if all(
        service['status'] == 'healthy' for service in services_health.values()
    ) else 'degraded'
    
    return jsonify({
        'status': overall_status,
        'services': services_health,
        'gateway': 'api-gateway'
    })

# Package Service Routes
@app.route('/api/packages', methods=['GET', 'POST'])
def packages():
    if request.method == 'GET':
        return proxy_request(PACKAGE_SERVICE_URL, '/packages', 'GET', params=request.args)
    else:
        return proxy_request(PACKAGE_SERVICE_URL, '/packages', 'POST', data=request.get_json())

@app.route('/api/packages/<package_id>', methods=['GET'])
def get_package(package_id):
    return proxy_request(PACKAGE_SERVICE_URL, f'/packages/{package_id}', 'GET')

@app.route('/api/packages/tracking/<tracking_number>', methods=['GET'])
def track_package(tracking_number):
    return proxy_request(PACKAGE_SERVICE_URL, f'/packages/tracking/{tracking_number}', 'GET')

@app.route('/api/packages/<package_id>/status', methods=['PUT'])
def update_package_status(package_id):
    return proxy_request(PACKAGE_SERVICE_URL, f'/packages/{package_id}/status', 'PUT', data=request.get_json())

# Delivery Service Routes
@app.route('/api/deliveries', methods=['GET'])
def deliveries():
    return proxy_request(DELIVERY_SERVICE_URL, '/deliveries', 'GET', params=request.args)

@app.route('/api/deliveries/<delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    return proxy_request(DELIVERY_SERVICE_URL, f'/deliveries/{delivery_id}', 'GET')

@app.route('/api/deliveries/<delivery_id>/assign', methods=['PUT'])
def assign_delivery(delivery_id):
    return proxy_request(DELIVERY_SERVICE_URL, f'/deliveries/{delivery_id}/assign', 'PUT', data=request.get_json())

@app.route('/api/deliveries/<delivery_id>/status', methods=['PUT'])
def update_delivery_status(delivery_id):
    return proxy_request(DELIVERY_SERVICE_URL, f'/deliveries/{delivery_id}/status', 'PUT', data=request.get_json())

@app.route('/api/routes', methods=['GET', 'POST'])
def routes():
    if request.method == 'GET':
        return proxy_request(DELIVERY_SERVICE_URL, '/routes', 'GET', params=request.args)
    else:
        return proxy_request(DELIVERY_SERVICE_URL, '/routes', 'POST', data=request.get_json())

# User Service Routes
@app.route('/api/users', methods=['GET', 'POST'])
def users():
    if request.method == 'GET':
        return proxy_request(USER_SERVICE_URL, '/users', 'GET', params=request.args)
    else:
        return proxy_request(USER_SERVICE_URL, '/users', 'POST', data=request.get_json())

@app.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    return proxy_request(USER_SERVICE_URL, f'/users/{user_id}', 'GET')

@app.route('/api/users/login', methods=['POST'])
def login():
    return proxy_request(USER_SERVICE_URL, '/users/login', 'POST', data=request.get_json())

@app.route('/api/users/<user_id>/addresses', methods=['GET', 'POST'])
def user_addresses(user_id):
    if request.method == 'GET':
        return proxy_request(USER_SERVICE_URL, f'/users/{user_id}/addresses', 'GET')
    else:
        return proxy_request(USER_SERVICE_URL, f'/users/{user_id}/addresses', 'POST', data=request.get_json())

@app.route('/api/drivers', methods=['GET'])
def drivers():
    return proxy_request(USER_SERVICE_URL, '/drivers', 'GET')

# Aggregated endpoints
@app.route('/api/packages/<package_id>/full-details', methods=['GET'])
def get_package_full_details(package_id):
    """Get package details with delivery and user information"""
    try:
        # Get package details
        package_response = requests.get(f"{PACKAGE_SERVICE_URL}/packages/{package_id}")
        if package_response.status_code != 200:
            return jsonify({'error': 'Package not found'}), 404
        
        package_data = package_response.json()
        
        # Get delivery details
        delivery_response = requests.get(f"{DELIVERY_SERVICE_URL}/deliveries", 
                                       params={'package_id': package_id})
        delivery_data = delivery_response.json() if delivery_response.status_code == 200 else []
        
        # Get sender and recipient details
        sender_response = requests.get(f"{USER_SERVICE_URL}/users/{package_data['sender_id']}")
        recipient_response = requests.get(f"{USER_SERVICE_URL}/users/{package_data['recipient_id']}")
        
        result = {
            'package': package_data,
            'delivery': delivery_data[0] if delivery_data else None,
            'sender': sender_response.json() if sender_response.status_code == 200 else None,
            'recipient': recipient_response.json() if recipient_response.status_code == 200 else None
        }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
