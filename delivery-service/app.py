from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
import json
import pika
from datetime import datetime
import uuid
import threading

app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/delivery_service')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# RabbitMQ configuration
rabbitmq_url = os.getenv('RABBITMQ_URL', 'amqp://admin:admin@localhost:5672/')

def get_rabbitmq_connection():
    try:
        connection = pika.BlockingConnection(pika.URLParameters(rabbitmq_url))
        return connection
    except Exception as e:
        print(f"Failed to connect to RabbitMQ: {e}")
        return None

# Delivery Model
class Delivery(db.Model):
    __tablename__ = 'deliveries'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    package_id = db.Column(db.String(36), nullable=False)
    driver_id = db.Column(db.String(36), nullable=True)
    pickup_address = db.Column(db.Text, nullable=False)
    delivery_address = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, assigned, picked_up, in_transit, delivered
    estimated_delivery = db.Column(db.DateTime, nullable=True)
    actual_delivery = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'package_id': self.package_id,
            'driver_id': self.driver_id,
            'pickup_address': self.pickup_address,
            'delivery_address': self.delivery_address,
            'status': self.status,
            'estimated_delivery': self.estimated_delivery.isoformat() if self.estimated_delivery else None,
            'actual_delivery': self.actual_delivery.isoformat() if self.actual_delivery else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class DeliveryRoute(db.Model):
    __tablename__ = 'delivery_routes'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    driver_id = db.Column(db.String(36), nullable=False)
    route_name = db.Column(db.String(100), nullable=False)
    deliveries = db.Column(db.JSON, nullable=False)  # List of delivery IDs
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'driver_id': self.driver_id,
            'route_name': self.route_name,
            'deliveries': self.deliveries,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

def publish_event(event_type, data):
    """Publish events to RabbitMQ"""
    try:
        connection = get_rabbitmq_connection()
        if connection:
            channel = connection.channel()
            
            # Declare exchange
            channel.exchange_declare(exchange='parcel_events', exchange_type='topic')
            
            # Publish message
            message = {
                'event_type': event_type,
                'timestamp': datetime.utcnow().isoformat(),
                'data': data
            }
            
            channel.basic_publish(
                exchange='parcel_events',
                routing_key=f'delivery.{event_type}',
                body=json.dumps(message)
            )
            
            connection.close()
            print(f"Published event: {event_type}")
    except Exception as e:
        print(f"Failed to publish event: {e}")

def consume_package_events():
    """Consume package events from RabbitMQ"""
    try:
        connection = get_rabbitmq_connection()
        if connection:
            channel = connection.channel()
            
            # Declare exchange and queue
            channel.exchange_declare(exchange='parcel_events', exchange_type='topic')
            result = channel.queue_declare(queue='delivery_service_queue', durable=True)
            queue_name = result.method.queue
            
            # Bind queue to exchange
            channel.queue_bind(exchange='parcel_events', queue=queue_name, routing_key='package.*')
            
            def callback(ch, method, properties, body):
                try:
                    message = json.loads(body)
                    event_type = message['event_type']
                    data = message['data']
                    
                    if event_type == 'created':
                        # Create delivery record when package is created
                        with app.app_context():
                            delivery = Delivery(
                                package_id=data['id'],
                                pickup_address=data['sender_address'],
                                delivery_address=data['recipient_address']
                            )
                            db.session.add(delivery)
                            db.session.commit()
                            print(f"Created delivery for package {data['id']}")
                    
                    ch.basic_ack(delivery_tag=method.delivery_tag)
                    
                except Exception as e:
                    print(f"Error processing message: {e}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            
            channel.basic_consume(queue=queue_name, on_message_callback=callback)
            print("Started consuming package events...")
            channel.start_consuming()
            
    except Exception as e:
        print(f"Failed to consume events: {e}")

# Routes
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'delivery-service'})

@app.route('/deliveries', methods=['GET'])
def get_deliveries():
    try:
        deliveries = Delivery.query.all()
        return jsonify([delivery.to_dict() for delivery in deliveries])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/deliveries/<delivery_id>', methods=['GET'])
def get_delivery(delivery_id):
    try:
        delivery = Delivery.query.get_or_404(delivery_id)
        return jsonify(delivery.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/deliveries/<delivery_id>/assign', methods=['PUT'])
def assign_delivery(delivery_id):
    try:
        data = request.get_json()
        delivery = Delivery.query.get_or_404(delivery_id)
        
        delivery.driver_id = data['driver_id']
        delivery.status = 'assigned'
        delivery.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Publish delivery assigned event
        publish_event('assigned', delivery.to_dict())
        
        return jsonify(delivery.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/deliveries/<delivery_id>/status', methods=['PUT'])
def update_delivery_status(delivery_id):
    try:
        data = request.get_json()
        delivery = Delivery.query.get_or_404(delivery_id)
        
        old_status = delivery.status
        delivery.status = data['status']
        delivery.updated_at = datetime.utcnow()
        
        if data['status'] == 'delivered':
            delivery.actual_delivery = datetime.utcnow()
        
        db.session.commit()
        
        # Publish status update event
        publish_event('status_updated', {
            'delivery_id': delivery_id,
            'package_id': delivery.package_id,
            'old_status': old_status,
            'new_status': delivery.status
        })
        
        return jsonify(delivery.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/deliveries', methods=['POST'])
def create_delivery_manual():
    try:
        data = request.get_json()
        
        delivery = Delivery(
            package_id=data['package_id'],
            pickup_address=data['pickup_address'],
            delivery_address=data['delivery_address'],
            driver_id=data.get('driver_id')
        )
        
        db.session.add(delivery)
        db.session.commit()
        
        # Publish delivery created event
        publish_event('created', delivery.to_dict())
        
        return jsonify(delivery.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/routes', methods=['POST'])
def create_route():
    try:
        data = request.get_json()
        
        route = DeliveryRoute(
            driver_id=data['driver_id'],
            route_name=data['route_name'],
            deliveries=data['deliveries']
        )
        
        db.session.add(route)
        db.session.commit()
        
        return jsonify(route.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/routes', methods=['GET'])
def get_routes():
    try:
        routes = DeliveryRoute.query.all()
        return jsonify([route.to_dict() for route in routes])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    # Start RabbitMQ consumer in a separate thread
    consumer_thread = threading.Thread(target=consume_package_events, daemon=True)
    consumer_thread.start()
    
    app.run(host='0.0.0.0', port=5000, debug=True)
