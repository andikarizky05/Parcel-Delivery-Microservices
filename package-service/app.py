from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
import os
import json
import pika
from datetime import datetime
import uuid

app = Flask(__name__)
CORS(app)

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/package_service')
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

# Package Model
class Package(db.Model):
    __tablename__ = 'packages'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tracking_number = db.Column(db.String(20), unique=True, nullable=False)
    sender_id = db.Column(db.String(36), nullable=False)
    recipient_id = db.Column(db.String(36), nullable=False)
    sender_address = db.Column(db.Text, nullable=False)
    recipient_address = db.Column(db.Text, nullable=False)
    weight = db.Column(db.Float, nullable=False)
    dimensions = db.Column(db.String(50), nullable=False)  # "LxWxH"
    status = db.Column(db.String(20), default='created')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'tracking_number': self.tracking_number,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'sender_address': self.sender_address,
            'recipient_address': self.recipient_address,
            'weight': self.weight,
            'dimensions': self.dimensions,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
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
                routing_key=f'package.{event_type}',
                body=json.dumps(message)
            )
            
            connection.close()
            print(f"Published event: {event_type}")
    except Exception as e:
        print(f"Failed to publish event: {e}")

# Routes
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'package-service'})

@app.route('/packages', methods=['POST'])
def create_package():
    try:
        data = request.get_json()
        
        # Generate tracking number
        tracking_number = f"PKG{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        package = Package(
            tracking_number=tracking_number,
            sender_id=data['sender_id'],
            recipient_id=data['recipient_id'],
            sender_address=data['sender_address'],
            recipient_address=data['recipient_address'],
            weight=data['weight'],
            dimensions=data['dimensions']
        )
        
        db.session.add(package)
        db.session.commit()
        
        # Publish package created event
        publish_event('created', package.to_dict())
        
        return jsonify(package.to_dict()), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@app.route('/packages', methods=['GET'])
def get_packages():
    try:
        packages = Package.query.all()
        return jsonify([package.to_dict() for package in packages])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/packages/<package_id>', methods=['GET'])
def get_package(package_id):
    try:
        package = Package.query.get_or_404(package_id)
        return jsonify(package.to_dict())
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/packages/tracking/<tracking_number>', methods=['GET'])
def get_package_by_tracking(tracking_number):
    try:
        package = Package.query.filter_by(tracking_number=tracking_number).first_or_404()
        return jsonify(package.to_dict())
    except Exception as e:
        return jsonify({'error': 'Package not found'}), 404

@app.route('/packages/<package_id>/status', methods=['PUT'])
def update_package_status(package_id):
    try:
        data = request.get_json()
        package = Package.query.get_or_404(package_id)
        
        old_status = package.status
        package.status = data['status']
        package.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        # Publish status update event
        publish_event('status_updated', {
            'package_id': package_id,
            'old_status': old_status,
            'new_status': package.status,
            'tracking_number': package.tracking_number
        })
        
        return jsonify(package.to_dict())
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
